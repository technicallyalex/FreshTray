"""Encrypted billing workspace, decimal arithmetic and source-safe imports.

Local records are never silently promoted into a connected account.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from email.message import EmailMessage
from email.policy import SMTP
from urllib.parse import quote, urlencode
import re
import uuid
import base64
import struct

CENT = Decimal('0.01')


def number(value, maximum='1000000000', places=None):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n > Decimal(maximum):
            raise ValueError()
        if places is not None and n != n.quantize(Decimal(1).scaleb(-places)):
            raise ValueError()
        return n
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Enter a nonnegative number within the allowed range.') from None


def money(value):
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def totals(invoice):
    discount = number(invoice.get('discount', 0), '100') / 100
    subtotal = Decimal(0); reduction = Decimal(0); tax = Decimal(0)
    amounts = []
    for line in invoice.get('lines', []):
        base = (number(line['qty']) * number(line['rate'], places=2)).quantize(CENT, rounding=ROUND_HALF_UP)
        cut = (base * discount).quantize(CENT, rounding=ROUND_HALF_UP)
        taxable = base-cut
        first = (taxable * number(line.get('tax', 0), '100')/100).quantize(CENT, rounding=ROUND_HALF_UP)
        second_base = taxable + first if line.get('compound') else taxable
        second = (second_base * number(line.get('tax2', 0), '100')/100).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += base; reduction += cut; tax += first+second; amounts.append(money(base))
    total = subtotal-reduction+tax
    paid = number(invoice.get('paid', 0))
    return dict(subtotal=money(subtotal), discount=money(reduction), tax=money(tax), total=money(total),
                paid=money(paid), balance=money(max(Decimal(0), total-paid)), amounts=amounts)


def validate(invoice):
    if not str(invoice.get('client', '')).strip():
        raise ValueError('Choose a client.')
    if '\r' in invoice.get('number','') or '\n' in invoice.get('number',''):
        raise ValueError('Invoice numbers must fit on one line.')
    issued = date.fromisoformat(invoice['date']); due = date.fromisoformat(invoice['due'])
    if due < issued:
        raise ValueError('The due date must be on or after the issue date.')
    if not re.fullmatch('[A-Z]{3}', invoice.get('currency', '')):
        raise ValueError('Enter a three-letter currency code, such as USD.')
    if not 1 <= len(invoice.get('lines', [])) <= 400:
        raise ValueError('An invoice needs between 1 and 400 lines.')
    for line in invoice['lines']:
        if not line.get('name', '').strip():
            raise ValueError('Every line needs an item or service name.')
        if number(line.get('qty')) <= 0:
            raise ValueError('Line quantities must be greater than zero.')
    calculated=totals(invoice)
    raw=(invoice.get('remote') or {}).get('raw',{})
    if invoice.get('sync')=='synced' and raw.get('amount',{}).get('amount') is not None:
        if Decimal(calculated['total'])!=number(raw['amount']['amount']):
            raise ValueError('FreshBooks reports a different invoice total. Review the tax/discount treatment in FreshBooks before exporting this invoice.')
    if any(len(str(invoice.get(k, ''))) > limit for k, limit in [('number', 40), ('note', 12000), ('terms', 12000), ('po', 200)]):
        raise ValueError('An invoice field is too long.')


def blank_line():
    return dict(name='', description='', qty='1', rate='0.00', tax='0', taxName='Tax', tax2='0', taxName2='', compound=False, sources=[])


def blank_invoice(client='', currency='USD'):
    today = date.today()
    return dict(id=uuid.uuid4().hex, client=str(client), number='', date=today.isoformat(),
                due=(today+timedelta(days=30)).isoformat(), currency=currency, discount='0', po='', note='',
                terms='Payment due within 30 days.', lines=[blank_line()], paid='0.00', status='Draft', sync='local', remote=None)


class BillingStore:
    def __init__(self, vault):
        self.vault = vault

    def data(self):
        return deepcopy(self._snapshot())

    def _snapshot(self):
        """Internal read-only snapshot; writers clone and atomically replace it."""
        return self.vault.get('billing_v1') or dict(seller=dict(name='', email='', address='', currency='USD'),
                    clients=[], projects=[], items=[], expenses=[], time=[], books={}, caches={}, sequence=0)

    def mutate(self, work):
        with self.vault.lock:
            data = self.data()
            result = work(data)
            self.vault.update(billing_v1=data)
            return deepcopy(result)

    def rows(self, namespace):
        return self.data()['books'].get(namespace, [])

    def put(self, namespace, invoice):
        validate(invoice)
        def work(d):
            rows = d['books'].setdefault(namespace, [])
            existing = next((x for x in rows if x['id'] == invoice['id']), None)
            if existing and existing.get('sync') in ('sending', 'review', 'conflict'):
                raise ValueError('Review this invoice’s sync outcome before changing it.')
            item = deepcopy(invoice)
            if namespace == 'local' and not item['number'].strip():
                used = {x['number'] for x in rows}
                candidate = 1
                while f'FT-{candidate:06}' in used: candidate += 1
                item['number'] = f'FT-{candidate:06}'
            if item['number'] and any(x['id'] != item['id'] and x['number'] == item['number'] for x in rows):
                raise ValueError('That invoice number is already in use.')
            wanted = [s for line in item['lines'] for s in line.get('sources', [])]
            if len(wanted) != len(set(wanted)):
                raise ValueError('A source entry appears more than once on this invoice.')
            used = {s for inv in rows if inv['id'] != item['id'] and not inv.get('deleted') for line in inv['lines'] for s in line.get('sources', [])}
            if used.intersection(wanted):
                raise ValueError('One of these entries is already reserved by another invoice.')
            if namespace == 'local':
                clients = {str(c['id']) for c in d['clients']}
                if item['client'] not in clients: raise ValueError('Choose an existing local client.')
                if not existing or existing['client']!=item['client'] or not item.get('client_snapshot'):
                    item['client_snapshot']=deepcopy(next(c for c in d['clients'] if str(c['id'])==item['client']))
                if not item.get('seller_snapshot') and d['seller']['name'].strip():item['seller_snapshot']=deepcopy(d['seller'])
                sources = {'time:'+str(x['id']):x for x in d['time']}
                sources.update({'expense:'+str(x['id']):x for x in d['expenses']})
                for source in wanted:
                    if source not in sources or str(sources[source]['client_id']) != item['client']:
                        raise ValueError('An imported entry no longer belongs to this client.')
            item['updated'] = datetime.now(timezone.utc).isoformat()
            if existing: rows[rows.index(existing)] = item
            else: rows.append(item)
            return item
        return self.mutate(work)

    def patch(self, namespace, invoice_id, **values):
        def work(d):
            inv = next(x for x in d['books'][namespace] if x['id'] == invoice_id)
            inv.update(deepcopy(values)); return inv
        return self.mutate(work)

    def cache(self, namespace, values):
        def work(d):
            previous=d['caches'].get(namespace,{})
            d['caches'][namespace]=dict(previous,**deepcopy(values))
        self.mutate(work)

    def used_sources(self, namespace, excluding=''):
        return {s for inv in self.rows(namespace) if inv['id'] != excluding and not inv.get('deleted')
                for line in inv['lines'] for s in line.get('sources', [])}

    def add(self, kind, values):
        if kind not in ('clients', 'projects', 'items', 'expenses'): raise ValueError('Unknown record type.')
        def work(d):
            existing=next((x for x in d[kind] if str(x['id'])==str(values.get('id',''))),None)
            if not existing:d['sequence'] += 1
            row = dict(existing or {}, **values)
            row['id']=existing['id'] if existing else d['sequence']
            if not row.get('name', '').strip(): raise ValueError('Enter a name.')
            if any(c in row['name'] for c in '\r\n'):raise ValueError('Names must fit on one line.')
            if kind in ('projects', 'expenses') and str(row.get('client_id')) not in {str(x['id']) for x in d['clients']}:
                raise ValueError('Choose a local client first.')
            if kind == 'expenses':
                date.fromisoformat(row['date']); row['amount'] = money(number(row['amount'], places=2))
                row.setdefault('currency',d['seller'].get('currency','USD'))
                if row.get('project_id') and not any(str(p['id'])==str(row['project_id']) and str(p['client_id'])==str(row['client_id']) for p in d['projects']):
                    raise ValueError('Choose a project for the same client.')
            if kind == 'items':
                row['rate'] = money(number(row['rate'], places=2))
                row.setdefault('currency',d['seller'].get('currency','USD'))
            if kind == 'clients' and row.get('email'): email_address(row['email'])
            if existing:d[kind][d[kind].index(existing)]=row
            else:d[kind].append(row)
            return row
        return self.mutate(work)


def import_lines(times, expenses, options, used=()):
    start, end = options.get('from', ''), options.get('to', '')
    if start: date.fromisoformat(start)
    if end: date.fromisoformat(end)
    if start and end and start > end: raise ValueError('The import end date must follow its start date.')
    projects = set(map(str, options.get('projects', [])))
    client = str(options['client']); used = set(used)
    includes = set(options.get('includes', ['service', 'project', 'member', 'date', 'notes']))
    rate = options.get('rate', '')
    override = number(rate, '1000000', 2) if str(rate).strip() else None
    def eligible(x, kind):
        return (str(x.get('client_id')) == client and not x.get('billed') and x.get('active', True)
                and kind+':'+str(x['id']) not in used and (not start or x['date'] >= start) and (not end or x['date'] <= end))
    groups = {}
    mode = options.get('format', 'detailed'); group = options.get('group', 'service')
    for row in sorted(times, key=lambda x:x['date']):
        if not eligible(row, 'time') or not row.get('billable', True) or not row.get('is_logged', True): continue
        if str(row.get('project_id') or '') not in projects: continue
        price = override if override is not None else number(row.get('rate', 0), places=2)
        key = str(row['id']) if mode == 'detailed' else str(row.get('project_id') or '') if mode == 'simple' else (str(row.get(group, '')), str(price))
        groups.setdefault(key, []).append((row, price))
    lines = []
    for rows in groups.values():
        seconds = sum(int(x['duration']) for x, _ in rows)
        hours = Decimal(seconds)/3600
        cost = sum(Decimal(x['duration'])/3600*p for x, p in rows).quantize(CENT, rounding=ROUND_HALF_UP)
        same = all(p == rows[0][1] for _, p in rows)
        first = rows[0][0]
        description = []
        for key in ('service', 'project', 'member', 'date', 'notes'):
            if key in includes: description.append(', '.join(dict.fromkeys(str(x.get(key) or ('No project' if key == 'project' else '')) for x,_ in rows)))
        if 'hours' in includes: description.append(f'{hours.quantize(Decimal("0.0001"))} hours')
        line = blank_line()
        name = first.get('project') or 'No project' if mode == 'simple' else first.get(group) or 'Time' if mode == 'grouped' else first.get('service') or 'Time'
        # A fixed total avoids rounding loss for mixed rates or fractional hours.
        quantity = str(hours) if same and hours*rows[0][1] == cost else '1'
        price = money(rows[0][1]) if quantity != '1' or same and hours == 1 else money(cost)
        if quantity == '1' and hours != 1: description.append(f'{seconds//3600}:{seconds%3600//60:02} hours · combined amount')
        line.update(name=str(name), description=' · '.join(filter(None, description)), qty=quantity, rate=price,
                    sources=['time:'+str(x['id']) for x,_ in rows], project_id=first.get('project_id'),
                    time_ids=[x['id'] for x,_ in rows])
        lines.append(line)
    expense_mode = options.get('expenses', 'all')
    for row in expenses:
        if not eligible(row, 'expense') or expense_mode == 'none': continue
        if expense_mode == 'selected' and str(row.get('project_id') or '') not in projects: continue
        if row.get('currency') and options.get('currency') and row['currency']!=options['currency']:
            raise ValueError('An expense uses a different currency. Exclude expenses or use a matching invoice currency.')
        line = blank_line(); line.update(name=row['name'], description=row['date'], rate=money(number(row['amount'], places=2)),
                expense_id=row['id'], sources=['expense:'+str(row['id'])]); lines.append(line)
    return lines


def email_address(value):
    value = str(value).strip()
    if len(value) > 254 or not re.fullmatch(r'[^\s<>\r\n,;?&#]+@[^\s<>\r\n,;?&#]+\.[^\s<>\r\n,;?&#]+', value):
        raise ValueError('Enter one valid client email address.')
    return value


def mailto(invoice, client, seller):
    recipient = email_address(client.get('email', ''))
    kind = 'Estimate' if invoice.get('kind') == 'estimate' else 'Invoice'
    subject = kind+' '+invoice['number']+' from '+seller['name']
    if '\r' in subject or '\n' in subject:raise ValueError('Invoice and business names must fit on one line.')
    body = f"Hello {client['name']},\r\n\r\nPlease find invoice {invoice['number']} for {totals(invoice)['total']} {invoice['currency']}, due {invoice['due']}.\r\n\r\n[Attach the exported invoice PDF before sending.]\r\n\r\n{seller['name']}\r\n{seller.get('email','')}"
    if kind == 'Estimate':
        body = f"Hello {client['name']},\r\n\r\nPlease see the attached estimate {invoice['number']} for {totals(invoice)['total']} {invoice['currency']}.\r\n\r\n[Attach the exported estimate PDF.]\r\n\r\n{seller['name']}"
    return 'mailto:'+quote(recipient, safe='@')+'?'+urlencode(dict(subject=subject, body=body), quote_via=quote)


def email_file(invoice, client, seller, pdf):
    message = EmailMessage(policy=SMTP)
    message['To'] = email_address(client.get('email', ''))
    if seller.get('email'): message['From'] = email_address(seller['email'])
    message['Subject'] = 'Invoice '+invoice['number']+' from '+seller['name']
    message['X-Unsent'] = '1'
    message.set_content(f"Hello {client['name']},\n\nPlease find your invoice attached.\nTotal: {totals(invoice)['total']} {invoice['currency']}\nDue: {invoice['due']}\n\n{seller['name']}")
    message.add_attachment(pdf, maintype='application', subtype='pdf', filename='Invoice.pdf')
    return message.as_bytes()


def invoice_html(invoice, client, seller):
    t = totals(invoice); e = lambda s:escape(str(s or '')).replace('\n', '<br>')
    estimate = invoice.get('kind') == 'estimate'
    kind = 'Estimate' if estimate else 'Invoice'
    date_extra = '' if estimate else f"<br><br><span class='muted'>Due Date</span><br>{e(invoice['due'])}"
    payment_summary = '' if estimate else f"Paid: {t['paid']}<br><b>Balance due: {t['balance']}</b>"
    logo=seller.get('logo','')
    brand=f'<h1>{kind.upper()}</h1>'
    if logo.startswith('data:image/png;base64,'):
        try:
            width,height=struct.unpack('>II',base64.b64decode(logo.split(',',1)[1],validate=True)[16:24])
            scale=min(180/width,90/height)
            brand=f'<img src="{escape(logo,quote=True)}" width="{max(1,round(width*scale))}" height="{max(1,round(height*scale))}"><br>{kind.upper()}'
        except (ValueError,struct.error,ZeroDivisionError):pass
    rows = ''.join(f"<tr><td width='62%'><b>{e(l['name'])}</b><br>{e(l.get('description'))}</td><td width='13%' align='right'>{e(l['rate'])}</td><td width='10%' align='right'>{e(l['qty'])}</td><td width='15%' align='right'>{t['amounts'][i]}</td></tr>" for i,l in enumerate(invoice['lines']))
    return f"""<html><head><meta charset='utf-8'><style>
body{{font-family:'IBM Plex Sans','Segoe UI';font-size:10pt;color:#062b54}}h1{{font-size:25pt;color:#0075dd}}td,th{{padding:8px}}table{{width:100%;border-collapse:collapse}}th{{border-bottom:1px solid #a7bad0;text-align:left}}tr{{page-break-inside:avoid}}.muted{{color:#657c94}}
</style></head><body><table width="100%" cellspacing="0" cellpadding="5"><tr><td width="50%">{brand}<br><span class='muted'>{e(invoice.get('status','Draft'))}</span></td><td width='50%' align='right'><h2>{e(seller.get('name'))}</h2>{e(seller.get('address'))}<br>{e(seller.get('email'))}</td></tr></table>
<p>&nbsp;</p>
<table width="100%" cellspacing="0" cellpadding="5"><tr><td width='30%'><span class='muted'>{'Prepared for' if estimate else 'Billed To'}</span><br><b>{e(client.get('name'))}</b><br>{e(client.get('address'))}<br>{e(client.get('email'))}</td><td width='23%'><span class='muted'>Date of Issue</span><br>{e(invoice['date'])}{date_extra}</td><td width='22%'><span class='muted'>{kind} Number</span><br>{e(invoice['number'])}<br><br><span class='muted'>Purchase Order</span><br>{e(invoice.get('po'))}</td><td width='25%' align='right'><span class='muted'>{'Estimate total' if estimate else 'Amount Due'} ({e(invoice['currency'])})</span><h1>{t['total'] if estimate else t['balance']}</h1></td></tr></table>
<p>&nbsp;</p>
<table width="100%" cellspacing="0" cellpadding="5"><thead><tr><th width='62%'>Description</th><th width='13%'>Rate</th><th width='10%'>Qty</th><th width='15%'>Line Total</th></tr></thead><tbody>{rows}</tbody></table>
<table width="100%" cellspacing="0" cellpadding="5"><tr><td width='55%'></td><td width='45%' align='right'>Subtotal: {t['subtotal']}<br>Discount: −{t['discount']}<br>Tax: {t['tax']}<h2>Total: {t['total']} {e(invoice['currency'])}</h2>{payment_summary}</td></tr></table>
<h3>Notes</h3><p>{e(invoice.get('note'))}</p><h3>{'Terms' if estimate else 'Payment terms'}</h3><p>{e(invoice.get('terms'))}</p></body></html>"""

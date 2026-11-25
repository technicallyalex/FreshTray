"""FreshBooks invoice read/write adapter with preserved invoice line metadata."""
from copy import deepcopy
from datetime import date, timedelta
from urllib.parse import quote, urlencode, urlsplit
import hashlib
import json
from .billing import blank_invoice, blank_line, money, number
from .api import ApiError


def signature(raw):
    return hashlib.sha256(json.dumps({'version':raw['version']} if raw.get('version') else {k:raw.get(k) for k in ('customerid','create_date','due_date','invoice_number','currency_code','discount_value','notes','terms','lines','paid','status','vis_state')}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class InvoiceAPI:
    def __init__(self, api, business):
        self.api = api; self.business = deepcopy(business)
        self.base = '/accounting/account/'+quote(str(business['account_id']), safe='')
        self.path = self.base+'/invoices/invoices'

    def get(self, invoice_id):
        return self.api.request('GET', self.path+'/'+str(int(invoice_id))+'?include[]=lines')['response']['result']['invoice']

    def catalog(self):
        clients, projects, services, warnings = self.api.catalog(self.business)
        # Invoice imports must not omit completed projects with unbilled time.
        projects = self.api.pages('/projects/business/'+str(int(self.business['id']))+'/projects','projects')
        items = self.api.pages(self.base+'/items/items', 'items', True)
        return dict(clients=[dict(id=str(c.get('id', c.get('userid'))), name=c.get('organization') or (c.get('fname','')+' '+c.get('lname','')).strip() or 'Unnamed client',
                    email=c.get('email',''), address='\n'.join(filter(None,[c.get('street'),c.get('city'),c.get('country')]))) for c in clients],
                    projects=[dict(p, name=p.get('title','Project')) for p in projects], services=services,
                    items=[dict(id=str(x.get('id',x.get('itemid'))),name=x.get('name','Item'),description=x.get('description',''),rate=x.get('unit_cost',{}).get('amount','0'),currency=x.get('unit_cost',{}).get('code','')) for x in items], warnings=warnings)

    def invoices(self):
        return self.api.pages(self.path+'?include[]=lines&include[]=presentation&include[]=system', 'invoices', True)

    def branding(self,rows):
        from .invoice_images import normalized_logo
        business=self.business
        address=business.get('address') or {}
        seller=dict(name=business.get('name',''),email='',phone=business.get('phone_number') or '',currency='',address='\n'.join(str(address.get(k) or '') for k in ('street','street2','city','province','postal_code','country') if address.get(k)))
        warnings=[]
        newest=sorted(rows,key=lambda r:str(r.get('updated') or r.get('create_date','')),reverse=True)
        system=next((r['system'] for r in newest if isinstance(r.get('system'),dict) and r['system'].get('name')),None)
        if not system:
            try:system=self.api.request('GET',self.base+'/systems/systems/'+quote(str(business['account_id']),safe=''))['response']['result']['system']
            except (ApiError,KeyError):warnings.append('Some business details require Business read access. Reconnect using the setup wizard if needed.')
        if system:
            for dest,keys in {'name':['name'],'email':['info_email','email'],'phone':['bus_phone','mob_phone'],'currency':['currency_code']}.items():
                value=next((system[k] for k in keys if system.get(k)),None)
                if value:seller[dest]=str(value)
            full='\n'.join(str(system[k]) for k in ('street','street2','city','province','code','country') if system.get(k))
            if full:seller['address']=full
        path=next(((r.get('presentation') or {}).get('image_logo_src') for r in newest if (r.get('presentation') or {}).get('image_logo_src')),None)
        if path:
            try:
                url=urlsplit(path)
                if url.netloc:
                    if url.scheme!='https' or url.netloc!='api.freshbooks.com':raise ValueError('Unsupported logo host')
                    path=url.path+('?' +url.query if url.query else '')
                seller['logo']=normalized_logo(self.api.image(path))
            except (ApiError,ValueError):warnings.append('The logo could not be refreshed. Keep the cached logo or choose one locally; reconnect with Uploads read access if needed.')
        return seller,warnings

    def sources(self, client, start='', end=''):
        args = dict(client_id=int(client), billable='true', billed='false', include_deleted='false', include_unlogged='false', team='true')
        # Server boundaries are deliberately broad; the import enforces local dates.
        if start: args['started_from']=(date.fromisoformat(start)-timedelta(days=1)).isoformat()+'T00:00:00Z'
        if end: args['started_to']=(date.fromisoformat(end)+timedelta(days=2)).isoformat()+'T00:00:00Z'
        times = self.api.pages('/timetracking/business/'+str(int(self.business['id']))+'/time_entries?'+urlencode(args), 'time_entries')
        expenses = self.api.pages(self.base+'/expenses/expenses?'+urlencode({'search[clientid]':int(client),'include[]':'project'}), 'expenses', True)
        return times, expenses

    def payload(self, invoice):
        fields = dict(customerid=int(invoice['client']), create_date=invoice['date'],
                      due_offset_days=(date.fromisoformat(invoice['due'])-date.fromisoformat(invoice['date'])).days,
                      currency_code=invoice['currency'], discount_value=str(invoice['discount']), po_number=invoice.get('po',''),
                      notes=invoice.get('note',''), terms=invoice.get('terms',''))
        if invoice['number'].strip(): fields['invoice_number'] = invoice['number'].strip()
        if invoice.get('source_estimate_remote'):
            fields['estimateid'] = int(invoice['source_estimate_remote'])
        rows = []
        for line in invoice['lines']:
            # Preserve IDs, linkage and existing tax metadata, never amount/read-only totals.
            raw = deepcopy(line.get('raw') or {})
            for key in ('amount','updated','invoiceid'): raw.pop(key, None)
            raw.update(name=line['name'], description=line.get('description',''), qty=str(line['qty']),
                       unit_cost=dict(amount=money(number(line['rate'])),code=invoice['currency']),
                       taxName1=line.get('taxName','Tax') if number(line.get('tax',0)) else '', taxAmount1=str(line.get('tax',0)),
                       taxName2=(line.get('taxName2') or 'Tax 2') if number(line.get('tax2',0)) else '', taxAmount2=str(line.get('tax2',0)),compounded_tax=bool(line.get('compound')))
            if line.get('expense_id'): raw.update(type=1,expenseid=int(line['expense_id']))
            if line.get('time_ids'): raw['modern_time_entries'] = list(map(int,line['time_ids']))
            if line.get('project_id'): raw['modern_project_id'] = int(line['project_id'])
            rows.append(raw)
        fields['lines'] = rows
        return {'invoice':fields}

    def write(self, invoice):
        remote = invoice.get('remote')
        estimate = invoice.get('source_estimate_remote')
        if estimate and not remote:
            path = self.base + '/estimates/estimates/' + str(int(estimate)) + '?include[]=invoices'
            source = self.api.request('GET', path)['response']['result']['estimate']
            if source.get('invoices') or source.get('invoiced'):
                raise ValueError('This estimate already has a linked FreshBooks invoice. Download invoices before retrying.')
        if remote:
            current = self.get(remote['id'])
            if signature(current) != remote['signature']:
                raise ValueError('This invoice changed in FreshBooks. Download it and review your local changes before syncing.')
        response = self.api.request('PUT' if remote else 'POST',self.path+('/'+str(int(remote['id'])) if remote else ''),self.payload(invoice))
        raw = response.get('response',{}).get('result',{}).get('invoice',{})
        if not raw.get('invoiceid',raw.get('id')): raise ApiError('FreshBooks did not confirm the invoice ID.',uncertain=True)
        return raw


def normalized(raw):
    inv = blank_invoice(str(raw['customerid']), raw.get('currency_code','USD'))
    rid = raw.get('invoiceid',raw.get('id')); inv['id'] = 'remote-'+str(rid)
    inv.update(number=str(raw.get('invoice_number','')),date=raw['create_date'],
               due=raw.get('due_date') or (date.fromisoformat(raw['create_date'])+timedelta(days=int(raw.get('due_offset_days',0)))).isoformat(),
               discount=str(raw.get('discount_value') or 0),po=raw.get('po_number') or '', note=raw.get('notes') or '',terms=raw.get('terms') or '',
               paid=raw.get('paid',{}).get('amount','0'),status=str(raw.get('display_status') or raw.get('v3_status') or 'Draft').title(),
               sync='synced',remote=dict(id=rid,signature=signature(raw),raw=deepcopy(raw)))
    if raw.get('estimateid'):
        inv['source_estimate_remote'] = str(raw['estimateid'])
    inv['lines'] = []
    if raw.get('organization') or raw.get('fname'):
        inv['client_snapshot']=dict(name=raw.get('organization') or ' '.join(filter(None,[raw.get('fname'),raw.get('lname')])),email=raw.get('email') or '',
                                   address='\n'.join(filter(None,[raw.get('street'),raw.get('street2'),raw.get('city'),raw.get('province'),raw.get('country')])))
    for source in raw.get('lines',[]):
        line=blank_line();line.update(name=source.get('name') or 'Item',description=source.get('description') or '',qty=str(source.get('qty',1)),
                rate=str(source.get('unit_cost',{}).get('amount','0')),tax=str(source.get('taxAmount1') or 0),taxName=source.get('taxName1') or 'Tax',
                tax2=str(source.get('taxAmount2') or 0),taxName2=source.get('taxName2') or '',compound=bool(source.get('compounded_tax')),raw=deepcopy(source))
        tids=source.get('modern_time_entries') or []
        if tids and all(isinstance(x,(int,str)) for x in tids): line.update(time_ids=tids,sources=['time:'+str(x) for x in tids])
        if source.get('expenseid'):line.update(expense_id=source['expenseid'],sources=['expense:'+str(source['expenseid'])])
        inv['lines'].append(line)
    return inv

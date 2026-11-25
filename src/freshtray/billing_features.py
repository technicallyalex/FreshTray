"""Billing records and the FreshBooks adapter for clients, estimates and payments."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode
from uuid import uuid4

from .api import ApiError
from .billing import blank_invoice, email_address, money, number, totals, validate
from .invoice_api import InvoiceAPI, normalized

RESOURCES = {
    'clients': ('users/clients', 'client', ('userid', 'id')),
    'estimates': ('estimates/estimates', 'estimate', ('estimateid', 'id')),
    'payments': ('payments/payments', 'payment', ('logid', 'paymentid', 'id')),
}
PAYMENT_METHODS = ('Cash', 'Check', 'Bank Transfer', 'Credit Card', 'PayPal', 'Other')
ESTIMATE_STATUSES = {1: 'Draft', 2: 'Sent', 3: 'Viewed', 4: 'Replied', 5: 'Accepted', 6: 'Invoiced'}


def identity(kind, raw):
    return next((str(raw[key]) for key in RESOURCES[kind][2] if raw.get(key) is not None), '')


def client_values(values):
    fields = ('company', 'first', 'last', 'email', 'phone', 'street', 'street2', 'city',
              'region', 'postal', 'country', 'address')
    client = {name: str(values.get(name) or '').strip() for name in fields}
    client['name'] = (client['company'] or ' '.join(filter(None, [client['first'], client['last']]))
                      or str(values.get('name') or '').strip())
    if not client['name']:
        raise ValueError('Enter a company or contact name.')
    if any(len(value) > 500 or '\r' in value or '\n' in value
           for key, value in client.items() if key != 'address'):
        raise ValueError('Use a single line of up to 500 characters for each client field.')
    if client['email']:
        client['email'] = email_address(client['email'])
    if not client['address']:
        client['address'] = '\n'.join(filter(None, (client[k] for k in fields[5:-1])))
    return client


CLIENT_FIELDS = dict(company='organization', first='fname', last='lname', email='email',
                     phone='bus_phone', street='street', street2='street2', city='city',
                     region='province', postal='code', country='country')


def remote_client(raw):
    values = {key: raw.get(field) for key, field in CLIENT_FIELDS.items()}
    values['name'] = 'Unnamed client'
    email = values.pop('email', None) or ''
    return dict(client_values(values), email=email, id=identity('clients', raw),
                archived=str(raw.get('vis_state', 0)) not in ('0', 'None'),
                revision=raw.get('updated'), remote=True)


def new_estimate(client='', currency='USD'):
    estimate = blank_invoice(client, currency)
    estimate.update(kind='estimate', due=estimate['date'], terms='')
    return estimate


def remote_estimate(raw):
    key = identity('estimates', raw)
    estimate = normalized(dict(raw, id=key, invoiceid=key, paid={'amount': '0'},
                               lines=raw.get('lines') or [],
                               invoice_number=raw.get('estimate_number', ''),
                               display_status=ESTIMATE_STATUSES.get(raw.get('status'), raw.get('ui_status', 'Draft'))))
    estimate.update(kind='estimate', archived=bool(raw.get('vis_state') or raw.get('ext_archive')),
                    revision=raw.get('updated'), remote_id=key,
                    linked_remote=bool(raw.get('invoices') or raw.get('invoiced')))
    estimate.pop('remote', None)
    if raw.get('invoiced') or raw.get('ui_status') == 'invoiced':
        estimate['status'] = 'Invoiced'
    return estimate


def estimate_payload(api, estimate):
    invoice = deepcopy(estimate)
    for line in invoice['lines']:
        line.pop('raw', None)
    fields = api.payload(invoice)['invoice']
    fields.pop('due_offset_days')
    for line in fields['lines']:
        line.setdefault('type', 0)
    if fields.get('invoice_number'):
        fields['estimate_number'] = fields.pop('invoice_number')
    return fields


def invoice_from_estimate(estimate):
    if not estimate.get('client'):
        raise ValueError('Choose a client.')
    invoice = blank_invoice(estimate['client'], estimate['currency'])
    for field in ('client_snapshot', 'seller_snapshot', 'lines', 'discount', 'po', 'note', 'terms'):
        if field in estimate:
            invoice[field] = deepcopy(estimate[field])
    for line in invoice['lines']:
        for field in ('raw', 'sources', 'time_ids', 'expense_id', 'project_id'):
            line.pop(field, None)
    invoice['source_estimate'] = estimate['id']
    if estimate.get('remote_id'):
        invoice['source_estimate_remote'] = estimate['remote_id']
    return invoice


def payment_values(values, balance):
    amount = number(values.get('amount'), places=2)
    if amount <= 0 or amount > number(balance):
        raise ValueError('Enter an amount greater than zero and no more than the available balance.')
    received = date.fromisoformat(str(values.get('date', '')))
    method = str(values.get('method', ''))
    if method not in PAYMENT_METHODS:
        raise ValueError('Choose a payment method.')
    note = str(values.get('note', '')).strip()
    if len(note) > 1000:
        raise ValueError('Use up to 1,000 characters for the payment note.')
    return dict(amount=money(amount), date=received.isoformat(), method=method, note=note)


def remote_payment(raw):
    method = str(raw.get('type') or 'Other')
    amount = raw.get('amount') or {}
    editable = method in PAYMENT_METHODS and not any(
        raw.get(key) for key in ('orderid', 'gateway', 'gatewayid', 'creditid', 'from_credit',
                                 'bulk_paymentid', 'overpaymentid'))
    return dict(id=identity('payments', raw), amount=str(amount.get('amount', '0')),
                date=str(raw.get('date') or ''), method=method, note=str(raw.get('note') or ''),
                editable=editable, revision=raw.get('updated'), raw=raw)


def local_payment(invoice, values, payment_id='', remove=False):
    """Keep any legacy paid balance that predates the stored payment records."""
    invoice = deepcopy(invoice)
    records = invoice.setdefault('payments', [])
    recorded = sum((number(row['amount']) for row in records), Decimal(0))
    carry = max(Decimal(0), number(invoice.get('paid', 0)) - recorded)
    previous = next((row for row in records if row.get('id') == payment_id), None)
    if payment_id and previous is None:
        raise ValueError('This payment could not be found.')
    if previous:
        records.remove(previous)
    paid = carry + sum((number(row['amount']) for row in records), Decimal(0))
    if not remove:
        balance = max(Decimal(0), number(totals(invoice)['total']) - paid)
        entry = payment_values(values, balance)
        records.append(dict(entry, id=payment_id or uuid4().hex))
        paid += number(entry['amount'])
    invoice['paid'] = money(paid)
    invoice['status'] = ('Paid' if totals(invoice)['balance'] == '0.00' else 'Partial') if paid else 'Sent'
    return invoice


def migrate_payment_ids(invoice):
    for row in invoice.get('payments', []):
        row.setdefault('id', uuid4().hex)
        row.setdefault('method', 'Other')
        row.setdefault('note', '')


class BillingAPI(InvoiceAPI):
    def resource(self, kind, remote_id=''):
        path = self.base + '/' + RESOURCES[kind][0]
        return path + '/' + str(int(remote_id)) if remote_id else path

    def list_records(self, kind, **filters):
        include = [('include[]', 'lines'), ('include[]', 'invoices')] if kind == 'estimates' else []
        query = urlencode(include + [(f'search[{k}]', v) for k, v in filters.items()])
        return self.api.pages(self.resource(kind) + ('?' + query if query else ''), kind, True)

    def get_record(self, kind, remote_id):
        singular = RESOURCES[kind][1]
        query = '?include[]=lines&include[]=invoices' if kind == 'estimates' else ''
        return self.api.request('GET', self.resource(kind, remote_id) + query)['response']['result'][singular]

    def apply(self, operation):
        kind, payload = operation['kind'], operation['payload']
        target = operation['target']
        if target:
            current = self.get_record(kind, target)
            expected = operation.get('expected')
            if expected is not None and expected != current.get('updated'):
                raise ValueError('This record changed in FreshBooks. Refresh and review it before editing again.')
        if kind == 'payments':
            payload = dict(payload, send_client_notification=False)
            invoice = self.get(payload['invoiceid'])
            outstanding = (invoice.get('outstanding') or {}).get('amount')
            if outstanding is None:
                outstanding = number(invoice['amount']['amount']) - number(invoice['paid']['amount'])
            allowance = max(Decimal(0), Decimal(str(outstanding)))
            if target:
                if not remote_payment(current)['editable'] or str(current.get('invoiceid')) != str(payload['invoiceid']):
                    raise ValueError('This payment must be managed in FreshBooks.')
                allowance += number(current['amount']['amount'])
            if 'amount' in payload:
                payment_values(dict(amount=payload['amount']['amount'], date=payload['date'],
                                    method=operation['method'], note=payload.get('note', '')), allowance)
        result = self.api.request('PUT' if target else 'POST', self.resource(kind, target),
                                  {RESOURCES[kind][1]: payload})
        raw = result.get('response', {}).get('result', {}).get(RESOURCES[kind][1], {})
        if not raw and target and 'vis_state' in payload:
            raw = self.get_record(kind, target)
        if not identity(kind, raw):
            raise ApiError('FreshBooks did not confirm the record. Check it before retrying.', uncertain=True)
        return raw

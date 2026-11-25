"""Qt billing workspace. Connected changes are saved before explicit sync."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from .api import ApiError
from .billing import blank_line, invoice_html, mailto, number, totals, validate
from .billing_features import (BillingAPI, CLIENT_FIELDS, PAYMENT_METHODS, client_values,
                               estimate_payload, invoice_from_estimate, local_payment,
                               migrate_payment_ids, new_estimate, payment_values,
                               remote_client, remote_estimate, remote_payment)
from .invoice_api import normalized


class BillingTools(QObject):
    changed = Signal()

    def __init__(self, invoices):
        super().__init__(invoices)
        self.invoices = invoices
        self.owner = invoices.owner
        self.store = invoices.store
        self.estimate = None
        self.estimate_key = None
        self.preview = ''
        self.pdf = None
        self.notice = ''
        self.errors = {}
        self.context = None
        invoices.changed.connect(self.invoice_changed)

    def invoice_changed(self):
        key = self.namespace()
        if key != self.context:
            self.context = key
            self.notice = ''
            self.errors = {}
        self.changed.emit()

    def namespace(self):
        return self.invoices.namespace()

    def workspace(self, key=None, data=None):
        if data is None:
            return self.store._snapshot().get('billing_tools', {}).get(key or self.namespace(), {})
        return data.setdefault('billing_tools', {}).setdefault(key or self.namespace(), {})

    def remote(self):
        self.invoices.remote_api()
        return BillingAPI(self.owner.remote_api, self.owner.business)

    def clients(self, workspace):
        if self.invoices.local:
            return self.store._snapshot()['clients']
        return workspace.get('clients', self.invoices.catalogs()['clients'])

    def active_estimate(self):
        return self.estimate if self.estimate_key == self.namespace() else None

    @Property('QVariantMap', notify=changed)
    def state(self):
        key = self.namespace()
        ws = self.workspace(key)
        clients = sorted(self.clients(ws), key=lambda row: row['name'].casefold())
        names = {str(row['id']): row['name'] for row in clients}
        estimates = []
        for row in ws.get('estimates', []):
            try:
                total = totals(row)['total']
            except ValueError:
                total = '—'
            estimates.append(dict(id=row['id'], number=row['number'] or 'Unnumbered draft',
                                  client=row['client'], name=names.get(row['client'], 'Existing client'),
                                  status=row['status'], archived=bool(row.get('archived')),
                                  date=row['date'], total=total, currency=row['currency']))
        draft = self.active_estimate()
        try:
            calculated = totals(draft) if draft else {}
        except ValueError:
            calculated = {}
        invoice = self.invoices.draft or {}
        invoice_remote = str((invoice.get('remote') or {}).get('id') or '')
        payment_rows = ws.get('payments', {}).get(invoice_remote, []) if invoice_remote else invoice.get('payments', [])
        payment_list = [dict(id=row.get('id', ''), date=row.get('date', ''), amount=row['amount'],
                             method=row.get('method', 'Other'), note=row.get('note', ''),
                             editable=row.get('editable', not invoice_remote)) for row in payment_rows]
        pending = [dict(id=job['id'], kind=job['kind'], label=job['label'],
                        status='review' if job['status']=='sending' and not self.invoices.busy else job['status'],
                        issue=job.get('issue', '')) for job in ws.get('queue', [])]
        return dict(clients=deepcopy(clients), estimates=sorted(estimates, key=lambda row: (row['date'], row['number']), reverse=True),
                    estimate=deepcopy(draft or {}), totals=calculated, preview=self.preview if draft else '',
                    items=self.invoices.catalogs()['items'], pending=pending, payments=payment_list,
                    methods=list(PAYMENT_METHODS), date=date.today().isoformat(), notice=self.notice,
                    errors=dict(self.errors), local=self.invoices.local, busy=self.invoices.busy,
                    canPay=bool(invoice.get('id') and (self.invoices.local or
                                invoice_remote and invoice.get('sync')=='synced') and
                                invoice.get('status','').lower() not in ('void', 'voided') and
                                not invoice.get('deleted')))

    def error(self, exc):
        self.notice = str(exc) if isinstance(exc, (ApiError, ValueError, OSError)) else 'Could not complete this billing action.'
        self.changed.emit()

    def refresh_local_catalog(self):
        b = self.owner
        if b.business:
            b.api.clear()
            b.clients, b.projects, b.services, _ = b.api.catalog(b.business)
            b.sync_choices()
            b.emit()

    @Slot(str, 'QVariantMap')
    def saveClient(self, client_id, values):
        if self.invoices.busy:
            return
        try:
            previous = next((row for row in self.clients(self.workspace()) if str(row['id']) == client_id), {})
            if client_id and not previous:
                raise ValueError('This client is no longer available.')
            if client_id and not self.invoices.local and not previous.get('remote'):
                raise ValueError('Refresh clients from FreshBooks before editing this client.')
            client = client_values(dict(values))
            if self.invoices.local:
                self.store.add('clients', dict(client, id=client_id))
                self.refresh_local_catalog()
                self.notice = 'Client saved.'
            else:
                payload = {remote: client[local] for local, remote in CLIENT_FIELDS.items()}
                if not any(payload[k] for k in ('organization','fname','lname')):
                    payload['organization'] = client['name']
                self.enqueue('clients', 'Save client ' + client['name'], client_id, payload, previous)
            self.invoices.emit()
        except Exception as exc:
            self.error(exc)

    @Slot(str, bool)
    def archiveClient(self, client_id, archived):
        if self.invoices.busy:
            return
        try:
            existing = next(row for row in self.clients(self.workspace()) if str(row['id']) == client_id)
            if not self.invoices.local and not existing.get('remote'):
                raise ValueError('Refresh clients from FreshBooks before changing their status.')
            def action():
                try:
                    if self.invoices.local:
                        self.store.add('clients', dict(existing, archived=archived))
                        self.refresh_local_catalog()
                        self.notice = 'Client archived.' if archived else 'Client restored.'
                    else:
                        self.enqueue('clients', ('Archive ' if archived else 'Restore ') + existing['name'],
                                     client_id, {'vis_state': 2 if archived else 0}, existing)
                    self.invoices.emit()
                except Exception as exc:
                    self.error(exc)
            if archived:
                self.owner.confirm('Archive this client? They will disappear from active pickers. Existing records keep their client information.', action)
            else:
                action()
        except Exception as exc:
            self.error(exc)

    @Slot(str)
    def refresh(self, kind):
        if self.invoices.busy or self.invoices.local:
            return
        if kind == 'invoices':
            self.notice = ''
            self.invoices.download()
            return
        try:
            api = self.remote()
            key = self.namespace()
            invoice_id = str(((self.invoices.draft or {}).get('remote') or {}).get('id') or '')
            if kind == 'payments' and not invoice_id:
                return
            def work():
                if kind == 'clients':
                    raw = api.list_records(kind, vis_state=0) + api.list_records(kind, vis_state=2)
                    rows = {row['id']: row for row in map(remote_client, raw)}
                elif kind == 'estimates':
                    rows = {row['remote_id']: row for row in map(remote_estimate, api.list_records(kind))}
                elif kind in ('payments', 'allPayments'):
                    filters = {'invoiceid': invoice_id} if kind == 'payments' else {}
                    rows = [row for row in map(remote_payment, api.list_records('payments', **filters))
                            if not row['raw'].get('vis_state')]
                    if kind == 'payments':
                        updated_invoice = normalized(api.get(invoice_id))
                    else:
                        by_invoice = {}
                        for row in rows:
                            rid = row['raw'].get('invoiceid')
                            if rid:
                                by_invoice.setdefault(str(rid), []).append(row)
                else:
                    raise ValueError('Unknown billing resource.')
                def commit(data):
                    ws = self.workspace(key, data)
                    if kind == 'payments':
                        ws.setdefault(kind, {})[invoice_id] = rows
                        self.update_invoice(data, key, invoice_id, updated_invoice)
                    elif kind == 'allPayments':
                        ws['payments'] = by_invoice
                    elif kind == 'clients':
                        ws[kind] = list(rows.values())
                        self.update_clients(data, key, ws[kind])
                    else:
                        old = ws.get(kind, [])
                        keep = [row for row in old if not row.get('remote_id') or
                                row.get('archived') and row['remote_id'] not in rows]
                        ids = {row['remote_id']: row['id'] for row in old if row.get('remote_id')}
                        cached = {row['remote_id']:row for row in old if row.get('remote_id')}
                        for rid, row in list(rows.items()):
                            previous = cached.get(rid, {})
                            if previous.get('dirty'):
                                rows[rid] = previous
                            else:
                                row['id'] = ids.get(rid, row['id'])
                        ws[kind] = keep + list(rows.values())
                self.store.mutate(commit)
            def done(_):
                if kind == 'payments':
                    self.reload_invoice(key)
                if kind == 'clients':
                    self.invoices.emit()
                self.notice = {'clients':'Clients refreshed.', 'estimates':'Estimates refreshed.',
                               'allPayments':'Payment history refreshed.'}.get(kind, '')
                self.changed.emit()
            self.run(work, done, kind)
        except Exception as exc:
            self.error(exc)

    def run(self, work, done, kind):
        self.errors.pop(kind, None)
        self.notice = ''
        def safe_work():
            try:
                return True, work()
            except (ApiError, ValueError, OSError) as exc:
                return False, exc
        def finish(result):
            ok, value = result
            if ok:
                done(value)
            else:
                text = ('Check your app permissions in FreshBooks. If you already added them, revoke the old authorization in FreshBooks and reconnect.'
                        if isinstance(value, ApiError) and value.status in (401, 403) else str(value))
                self.errors[kind] = text
                self.notice = text
            self.changed.emit()
        self.invoices.job(safe_work, finish)

    def enqueue(self, kind, label, target, payload, previous=None, **links):
        key = self.namespace()
        def write(data):
            jobs = self.workspace(key, data).setdefault('queue', [])
            group = links.get('estimate_id') or links.get('invoice_id') or target
            if any(job['kind']==kind and (job.get('group')==group if group else job['payload']==payload) for job in jobs):
                raise ValueError('Review or sync the existing pending change first.')
            jobs.append(dict(id=uuid4().hex, kind=kind, label=label, target=target, payload=payload,
                             expected=(previous or {}).get('revision'), status='queued', group=group, **links))
        self.store.mutate(write)
        self.notice = 'Saved locally. Sync pending changes when ready.'
        self.changed.emit()

    @Slot()
    def sync(self):
        if self.invoices.busy or self.invoices.local:
            return
        try:
            key = self.namespace()
            api = self.remote()
            queued = [job for job in self.workspace(key).get('queue', []) if job['status']=='queued']
            def work():
                if queued and self.owner.offline and not self.owner.offline.probe():
                    raise ValueError('FreshBooks is unreachable. The changes are still queued on this device.')
                for job in queued:
                    def set_status(data, status, issue=''):
                        row = next(x for x in self.workspace(key, data)['queue'] if x['id']==job['id'])
                        row.update(status=status, issue=issue)
                    self.store.mutate(lambda data: set_status(data, 'sending'))
                    try:
                        raw = api.apply(job)
                        self.commit_remote(key, job, raw, api)
                    except Exception as exc:
                        if isinstance(exc, ApiError) and exc.status in (401, 403) and not exc.uncertain:
                            self.store.mutate(lambda data: set_status(data, 'queued'))
                            raise
                        self.store.mutate(lambda data: set_status(data, 'review',
                            'Check the current record in FreshBooks before discarding this pending operation. '
                            + (str(exc) if isinstance(exc, ValueError) else 'The outcome could not be confirmed.')))
                        return False
                return True
            def done(ok):
                self.reload_estimate()
                self.reload_invoice(key)
                self.notice = 'Pending changes confirmed by FreshBooks.' if ok else 'A change needs review before it can be retried.'
                if ok and any(job['kind']=='clients' for job in queued):
                    self.owner.api.clear('catalog')
                    self.owner.load_catalog(self.owner._s['businessIndex'])
            self.run(work, done, 'sync')
        except Exception as exc:
            self.error(exc)

    def commit_remote(self, key, job, raw, api):
        kind = job['kind']
        if kind == 'estimates':
            updated_estimate = remote_estimate(api.get_record(kind, job['target'] or raw.get('estimateid') or raw['id']))
        if kind == 'payments':
            rid = str(job['invoice_id'])
            updated_invoice = normalized(api.get(rid))
            payments = [row for row in map(remote_payment, api.list_records(kind, invoiceid=rid))
                        if not row['raw'].get('vis_state')]
        def commit(data):
            ws = self.workspace(key, data)
            if kind == 'clients':
                updated = remote_client(raw)
                rows = ws.setdefault(kind, self.invoices.catalogs()['clients'])
                rows[:] = [row for row in rows if str(row['id'])!=updated['id']] + [updated]
                self.update_clients(data, key, rows)
            elif kind == 'estimates':
                updated = updated_estimate
                rows = ws.setdefault(kind, [])
                updated['id'] = job['estimate_id']
                rows[:] = [row for row in rows if row['id']!=updated['id'] and row.get('remote_id')!=updated['remote_id']] + [updated]
            else:
                ws.setdefault(kind, {})[rid] = payments
                self.update_invoice(data, key, rid, updated_invoice)
            ws['queue'][:] = [row for row in ws['queue'] if row['id']!=job['id']]
        self.store.mutate(commit)

    def update_clients(self, data, key, clients):
        cache = data['caches'].setdefault(key, {})
        cache['clients'] = [row for row in clients if not row.get('archived')]

    def update_invoice(self, data, key, remote_id, updated):
        for row in data['books'].get(key, []):
            if str((row.get('remote') or {}).get('id')) == remote_id and row['sync']=='synced':
                row.update({k:v for k,v in updated.items() if k!='id'})

    def reload_invoice(self, key):
        current = self.invoices.draft
        if current and current.get('sync')=='synced' and key==self.namespace():
            matching = next((item for item in self.store._snapshot()['books'].get(key, [])
                             if item['id']==current['id']), None)
            if matching:
                self.invoices.draft = deepcopy(matching)
                self.invoices.base = deepcopy(matching)
                self.invoices.last_pdf = None
                self.invoices.emit()

    @Slot(str)
    def discard(self, job_id):
        if self.invoices.busy:
            return
        key = self.namespace()
        def action():
            try:
                def write(data):
                    ws = self.workspace(key, data)
                    ws['queue'] = [job for job in ws.get('queue', []) if job['id']!=job_id]
                self.store.mutate(write)
                self.notice = 'Pending change removed from this device.'
                self.changed.emit()
            except OSError as exc:
                self.error(exc)
        self.owner.confirm('Remove this pending change? If it needs review, first check the FreshBooks record to see whether the change already took effect.', action)

    def reload_estimate(self):
        draft = self.active_estimate()
        if draft:
            row = next((row for row in self.workspace().get('estimates', []) if row['id']==draft['id']), None)
            if row and row.get('remote_id'):
                self.estimate = deepcopy(row)
        self.changed.emit()

    @Slot(str)
    def openEstimate(self, key):
        if self.invoices.busy:
            return
        try:
            if key:
                estimate = next(row for row in self.workspace().get('estimates', []) if row['id']==key)
            else:
                client = next((row for row in self.clients(self.workspace()) if not row.get('archived')), {})
                estimate = new_estimate(str(client.get('id','')), self.invoices.seller_details().get('currency') or 'USD')
            self.estimate_key = self.namespace()
            self.estimate = deepcopy(estimate)
            self.preview = ''
            self.pdf = None
            self.notice = ''
            self.changed.emit()
        except Exception as exc:
            self.error(exc)

    @Slot()
    def closeEstimate(self):
        self.estimate = None
        self.preview = ''
        self.changed.emit()

    @Slot(str, str)
    def estimateField(self, key, value):
        row = self.active_estimate()
        if row and key in ('client', 'number', 'date', 'currency', 'discount', 'po', 'note', 'terms'):
            if row.get(key)==value:
                return
            if key=='client' and row[key]!=value:
                row.pop('client_snapshot', None)
            row[key] = value
            row['dirty'] = True
            self.preview = ''
            self.pdf = None
            self.changed.emit()

    @Slot(int, str, str)
    def estimateLine(self, index, key, value):
        row = self.active_estimate()
        if row and 0 <= index < len(row['lines']) and key in ('name','description','qty','rate','tax','tax2'):
            if row['lines'][index].get(key)==value:
                return
            row['lines'][index][key] = value
            row['dirty'] = True
            self.preview = ''
            self.pdf = None
            self.changed.emit()

    @Slot(str, int)
    def editEstimateLines(self, item_id, remove):
        row = self.active_estimate()
        if not row:
            return
        try:
            if remove >= 0:
                if len(row['lines']) > 1:
                    del row['lines'][remove]
            elif len(row['lines']) < 400:
                line = blank_line()
                if item_id:
                    item = next(item for item in self.invoices.catalogs()['items'] if str(item['id'])==item_id)
                    if item.get('currency') and item['currency']!=row['currency']:
                        raise ValueError('The saved item uses a different currency.')
                    line.update(name=item['name'], rate=item['rate'], description=item.get('description',''))
                    if len(row['lines'])==1 and not row['lines'][0]['name']:
                        row['lines'].clear()
                row['lines'].append(line)
            row['dirty'] = True
            self.preview = ''
            self.pdf = None
            self.changed.emit()
        except Exception as exc:
            self.error(exc)

    def estimate_parties(self, row):
        client = row.get('client_snapshot') or next((c for c in self.clients(self.workspace())
                                                      if str(c['id'])==row['client']), None)
        seller = row.get('seller_snapshot') or self.invoices.seller_details()
        if not client:
            raise ValueError('Choose an estimate client.')
        if not seller.get('name'):
            raise ValueError('Add your business details from Invoices.')
        return client, seller

    def save_estimate(self, row):
        row = deepcopy(row)
        row['due'] = row['date']
        validate(row)
        row['client_snapshot'], row['seller_snapshot'] = self.estimate_parties(row)
        key = self.namespace()
        def write(data):
            rows = self.workspace(key, data).setdefault('estimates', [])
            if not row['number'] and self.invoices.local:
                used = {record['number'] for record in rows}
                index = 1
                while f'EST-{index:06}' in used:
                    index += 1
                row['number'] = f'EST-{index:06}'
            if row['number'] and any(record['number']==row['number'] and record['id']!=row['id'] for record in rows):
                raise ValueError('That estimate number is already in use.')
            rows[:] = [record for record in rows if record['id']!=row['id']] + [row]
        self.store.mutate(write)
        self.estimate = row
        return row

    @Slot(str)
    def estimateAction(self, action):
        if self.invoices.busy or not self.active_estimate():
            return
        try:
            row = self.active_estimate()
            if action == 'web':
                if not QDesktopServices.openUrl(QUrl('https://my.freshbooks.com/#/estimates')):
                    raise ValueError('Open FreshBooks in your browser and select Estimates.')
                return
            if action == 'duplicate':
                row = deepcopy(row)
                row.update(id=uuid4().hex, number='', date=date.today().isoformat(), status='Draft', archived=False, sync='local')
                for field in ('remote_id','revision'):
                    row.pop(field, None)
                self.estimate = row
                self.preview = ''
                self.pdf = None
            elif action == 'save':
                self.save_estimate(row)
                self.notice = 'Estimate saved on this device.'
            elif action == 'sync':
                row = self.save_estimate(row)
                payload = estimate_payload(self.remote(), row)
                if row['client_snapshot'].get('email'):
                    payload['email'] = row['client_snapshot']['email']
                self.enqueue('estimates', 'Save estimate ' + row['number'], row.get('remote_id',''),
                             payload, row, estimate_id=row['id'])
            elif action in ('sent','accepted','archive','restore'):
                if not self.invoices.local and action in ('sent','accepted'):
                    raise ValueError('Manage sending and acceptance in FreshBooks.')
                row = deepcopy(self.save_estimate(row))
                if action in ('archive','restore'):
                    archived = action=='archive'
                    if not self.invoices.local and row.get('remote_id'):
                        self.enqueue('estimates', 'Archive estimate' if archived else 'Restore estimate', row['remote_id'],
                                     {'vis_state': 2 if archived else 0}, row, estimate_id=row['id'])
                    else:
                        row['archived'] = archived
                        self.save_estimate(row)
                else:
                    row['status'] = 'Sent' if action=='sent' else 'Accepted'
                    self.save_estimate(row)
            elif action == 'preview':
                row = self.save_estimate(row)
                self.preview = invoice_html(row, *self.estimate_parties(row))
            elif action == 'pdf':
                row = self.save_estimate(row)
                path, _ = QFileDialog.getSaveFileName(None,'Export estimate PDF','Estimate.pdf','PDF (*.pdf)')
                if path:
                    self.pdf = Path(path if path.lower().endswith('.pdf') else path+'.pdf')
                    self.invoices.render_pdf(self.pdf, invoice_html(row, *self.estimate_parties(row)))
                    self.notice = 'Estimate PDF exported.'
            elif action == 'email':
                if not self.pdf or not self.pdf.is_file():
                    raise ValueError('Export an estimate PDF first, then attach it in your mail app.')
                if not QDesktopServices.openUrl(QUrl(mailto(row, *self.estimate_parties(row)))):
                    raise ValueError('No default mail app is available.')
            elif action == 'convert':
                self.convert(row)
            self.changed.emit()
        except Exception as exc:
            self.error(exc)

    def convert(self, row):
        if not self.invoices.local and not row.get('remote_id'):
            raise ValueError('Sync the estimate before creating a linked FreshBooks invoice.')
        key = self.namespace()
        def matches(inv):
            return inv.get('source_estimate')==row['id'] or (
                row.get('remote_id') and inv.get('source_estimate_remote')==row['remote_id'])
        existing = next((inv for inv in self.store._snapshot()['books'].get(key, []) if matches(inv)), None)
        if existing:
            self.invoices.openInvoice(existing['id'])
            self.owner.selectPanel('invoices')
            return
        if row['status']=='Invoiced' or row.get('linked_remote'):
            raise ValueError('This estimate already has a linked invoice in FreshBooks. Download invoices first.')
        def action():
            try:
                if key != self.namespace():
                    return
                if not self.invoices.persist_draft():
                    return
                existing = next((inv for inv in self.store._snapshot()['books'].get(key, []) if matches(inv)), None)
                if existing:
                    self.invoices.openInvoice(existing['id'])
                    self.owner.selectPanel('invoices')
                    return
                estimate = self.save_estimate(row)
                inv = invoice_from_estimate(estimate)
                inv['sync'] = 'local'
                inv = self.store.put(key, inv)
                self.invoices.openInvoice(inv['id'])
                self.owner.selectPanel('invoices')
            except Exception as exc:
                self.error(exc)
        self.owner.confirm('Create an invoice draft from this estimate? Review the copied lines and totals before syncing or sharing it.', action)

    @Slot(str, 'QVariantMap', bool)
    def recordPayment(self, payment_id, values, remove):
        inv = self.invoices.draft
        if not inv or self.invoices.busy:
            return
        try:
            if inv.get('deleted') or inv.get('status','').lower() in ('void','voided'):
                raise ValueError('Payments cannot be changed on this invoice.')
            if self.invoices.local:
                self.invoices.prepare_export()
                inv = deepcopy(self.invoices.draft)
                migrate_payment_ids(inv)
                updated = local_payment(inv, dict(values), payment_id, remove)
                self.invoices.draft = self.store.patch(self.namespace(), inv['id'], **{k:v for k,v in updated.items() if k!='id'})
                self.invoices.last_pdf = None
                self.invoices.persist_draft()
                self.notice = 'Payment history updated.'
                self.invoices.emit()
                return
            if not inv.get('remote') or inv['sync']!='synced':
                raise ValueError('Sync the invoice before recording a FreshBooks payment.')
            rid = str(inv['remote']['id'])
            old = next((row for row in self.workspace().get('payments',{}).get(rid,[]) if row['id']==payment_id), None)
            if payment_id and (not old or not old['editable']):
                raise ValueError('Manage this payment in FreshBooks.')
            if remove:
                payload = dict(invoiceid=int(rid), vis_state=1)
                method = ''
            else:
                raw = inv['remote'].get('raw',{})
                balance = number((raw.get('outstanding') or {}).get('amount', totals(inv)['balance']))
                if old:
                    balance += number(old['amount'])
                item = payment_values(dict(values), balance)
                method = item['method']
                payload = dict(invoiceid=int(rid), date=item['date'], type=method, note=item['note'],
                               amount=dict(amount=item['amount'], code=inv['currency']))
            self.enqueue('payments', 'Remove payment' if remove else ('Update payment' if old else 'Record payment') +
                         ' for invoice ' + inv['number'], payment_id, payload, old, invoice_id=rid, method=method)
        except Exception as exc:
            self.error(exc)

    @Slot()
    def preparePayments(self):
        inv = self.invoices.draft
        if not inv or self.invoices.busy:
            return
        try:
            self.notice = ''
            if self.invoices.local:
                if any(not row.get('id') for row in inv.get('payments', [])):
                    inv = deepcopy(inv)
                    migrate_payment_ids(inv)
                    self.invoices.draft = self.store.patch(self.namespace(), inv['id'], payments=inv['payments'])
                    self.invoices.persist_draft()
                self.changed.emit()
            else:
                self.refresh('payments')
        except Exception as exc:
            self.error(exc)

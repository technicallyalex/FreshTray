"""Real standalone time tracking; no sockets, tokens or sample records."""
from copy import deepcopy
from .billing import BillingStore
from .history_model import month_entries, entry_signature, edit_restriction
from .api import ApiError


class LocalProvider:
    connected = True
    local_mode = True
    transport = None

    def __init__(self, vault):
        self.store = BillingStore(vault)

    def profile(self):
        name = self.store.data()['seller']['name'] or 'Local business'
        return dict(id=-1001, first_name='Local', last_name='workspace', business_memberships=[
            dict(role='owner', business=dict(id=-1001, account_id='local', name=name, active=True))])

    def catalog(self, business):
        data = self.store.data()
        clients = [dict(x, organization=x['name']) for x in data['clients'] if not x.get('archived')]
        client_ids = {str(x['id']) for x in clients}
        projects = [dict(x, title=x['name'], services=[]) for x in data['projects'] if str(x['client_id']) in client_ids]
        return clients, projects, [], []

    def submit(self, business, payload):
        return self._submit(business,payload)

    def submit_timer(self,business,payload,request_id):
        import uuid
        uuid.UUID(request_id)
        return self._submit(business,payload,request_id)

    def _submit(self,business,payload,request_id=None):
        def work(d):
            existing=d.get('timer_receipts',{}).get(request_id) if request_id else None
            if existing:
                if existing['payload']!=payload:raise ValueError('The saved timer request does not match this entry.')
                return next(x for x in d['time'] if x['id']==existing['id'])
            row = deepcopy(payload['time_entry'])
            if str(row['client_id']) not in {str(c['id']) for c in d['clients']}:
                raise ValueError('Add a local client in Invoices > Local records first.')
            d['sequence'] += 1
            row.update(id=d['sequence'], active=True)
            d['time'].append(row)
            d['last_saved_time']=dict(business_id=business,payload=deepcopy(payload),id=row['id'])
            if request_id:d.setdefault('timer_receipts',{})[request_id]=dict(payload=deepcopy(payload),id=row['id'])
            return row
        return self.store.mutate(work)

    @property
    def local_last_success(self):return self.store.data().get('last_saved_time')

    def timer_submission_state(self,request_id):return 'saved' if request_id in self.store.data().get('timer_receipts',{}) else 'absent'

    def forget_timer_receipt(self,request_id):self.store.mutate(lambda d:d.setdefault('timer_receipts',{}).pop(request_id,None))

    def entries_for_month(self, business, month, identity):
        return deepcopy(month_entries(self._entries(), month, identity))

    def _entries(self):
        used = self.store.used_sources('local')
        return [dict(row, billed='time:'+str(row['id']) in used) for row in self.store.data()['time']]

    def get_entry(self, business, entry_id):
        return next((x for x in self._entries() if str(x['id']) == str(entry_id)), None)

    def _check(self, business, entry_id, original):
        current = self.get_entry(business, entry_id)
        if not current or entry_signature(current) != entry_signature(original):
            raise ApiError('The local entry changed. Reload it before continuing.')
        if edit_restriction(current): raise ApiError(edit_restriction(current))

    def update_entry(self, business, entry_id, payload, original):
        with self.store.vault.lock:
            self._check(business, entry_id, original)
            def work(d):
                row = next(x for x in d['time'] if str(x['id']) == str(entry_id))
                row.update(deepcopy(payload['time_entry'])); return row
            return self.store.mutate(work)

    def delete_entry(self, business, entry_id, original, identity):
        with self.store.vault.lock:
            self._check(business, entry_id, original)
            def work(d):
                row = next(x for x in d['time'] if str(x['id']) == str(entry_id))
                row['active'] = False
                return dict(deleted=True, id=entry_id, business_id=business)
            return self.store.mutate(work)

    def check_pending(self): return None

    def disconnect(self): raise ValueError('Standalone mode has no FreshBooks connection to disconnect.')

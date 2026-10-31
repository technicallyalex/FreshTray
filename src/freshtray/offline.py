"""Encrypted offline snapshots and a durable, serialized outbox.

Never retries an ambiguous create automatically. The provider's pending journal
remains the authority for whether a network write might already have happened.
"""
from copy import deepcopy
from datetime import date
import http.client
import threading
import time
import uuid
from functools import wraps

from .api import ApiError
from .history_model import entry_date, entry_signature, edit_restriction, month_entries
from .model import matching_entry


def reachable():
    connection = http.client.HTTPSConnection('api.freshbooks.com', timeout=4)
    try:
        connection.request('HEAD', '/')  # No credentials, payload or third-party probe.
        response = connection.getresponse()
        response.read(1024)
        return True
    except OSError:
        return False
    finally:
        connection.close()


def locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call


class OfflineAPI:
    def __init__(self, backend, vault, store, probe=reachable):
        self.backend, self.vault, self.store, self.probe = backend, vault, store, probe
        self.lock = threading.RLock()
        self.sync_lock = threading.Lock()
        self.stopping = threading.Event()
        self.data = deepcopy(store.get('offline_v1') or dict(profile=None, catalogs={}, months={}, outbox=[], aliases={}, incomplete=[]))
        self.data.setdefault('incomplete', [])
        self.online, self.message, self.last_refresh = None, '', 0
        self.verified = False
        self.active_month = None

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def persist(self, data):
        pinned = {self._monthkey(o['business'], entry_date(o['entry']).replace(day=1), o['entry']['identity_id']) for o in data['outbox']}
        pinned.add(self.active_month if hasattr(self, 'active_month') else None)
        for key in list(data['months']):
            if len(data['months']) <= 24:
                break
            if key not in pinned:
                del data['months'][key]
        data['incomplete'] = [key for key in data.get('incomplete', []) if key in data['months']]
        self.store.update(offline_v1=data)
        self.data = data  # Publish only after the encrypted atomic write succeeds.

    def legacy_pending(self):
        pending = self.vault.get('pending')
        if not pending:
            return False
        for op in self.data['outbox']:
            if op['state'] not in ('sending', 'review'):
                continue
            if str(pending.get('business_id')) != str(op['business']) or pending.get('operation', 'create') != op['kind']:
                continue
            if op['kind'] == 'create' and pending.get('payload') == op['payload']:
                return False
            if op['kind'] != 'create' and str(pending.get('entry_id')) == str(op['entry']['id']):
                return False
        return True

    def status(self):
        data = self.data
        message = self.message or ('This month is not fully downloaded. Only cached and local changes are shown.' if self.active_month in data['incomplete'] else '')
        return dict(online=self.online, message=message, count=len(data['outbox']),
                    problems=[dict(id=o['qid'], action=o['kind'], day=entry_date(o['entry']).isoformat(),
                                   note=o['entry'].get('note', ''), status=o['state'], message=o.get('error', ''))
                              for o in data['outbox'] if o['state'] in ('review', 'conflict')])

    def _identity(self, profile):
        old = self.data.get('profile')
        pending_identity = ((self.vault.get('pending') or {}).get('payload') or {}).get('time_entry', {}).get('identity_id')
        expected = old['id'] if old else pending_identity
        if expected is not None and str(expected) != str(profile['id']):
            self.message = 'This connection belongs to a different FreshBooks account. Reconnect the original account; local changes are retained.'
            raise ApiError(self.message)
        self.verified = True

    def _read(self, group, key, work):
        with self.lock:
            if group == 'profile':
                saved = self.data.get('profile')
            else:
                saved = self.data[group].get(key)
            if saved is not None:
                return deepcopy(saved)
            if not self.probe():
                self.online = False
                raise ApiError('Offline: this data has not been downloaded yet. Connect once to make it available.')
            profile = self.backend.profile()
            self._identity(profile)
            result = profile if group == 'profile' else work()
            data = deepcopy(self.data)
            data['profile'] = profile
            if group != 'profile':
                if group == 'months' and len(data[group]) >= 24:
                    data[group].pop(next(iter(data[group])))
                data[group][key] = result
            self.persist(data)
            self.online = True
            return deepcopy(result)

    def profile(self):
        return self._read('profile', '', self.backend.profile)

    def catalog(self, business):
        key = str(business['id'])
        return self._read('catalogs', key, lambda: self.backend.catalog(business))

    def _monthkey(self, business, month, identity):
        return f'{business}/{identity}/{month.isoformat()}'

    def entries_for_month(self, business, month, identity):
        key = self._monthkey(business, month, identity)
        self.active_month = key
        try:
            entries = self._read('months', key, lambda: self.backend.entries_for_month(business, month, identity))
        except ApiError as exc:
            # A known account can record new time in an uncached month. Do not
            # pretend its existing server entries have already been downloaded.
            if not self.data.get('profile'):
                raise
            entries = []
            data = deepcopy(self.data)
            data['months'][key] = []
            if key not in data['incomplete']:
                data['incomplete'].append(key)
            self.persist(data)
            self.message = 'This month is incomplete: only locally saved changes are shown. ' + str(exc)
        return self.view_month(business, month, identity, entries)

    def view_month(self, business, month, identity, entries=None):
        if entries is None:
            entries = deepcopy(self.data['months'].get(self._monthkey(business, month, identity), []))
        result = {str(e['id']): deepcopy(e) for e in entries}
        for op in self.data['outbox']:
            if str(op['business']) != str(business):
                continue
            result.pop(str(op['entry']['id']), None)
            if op['kind'] != 'delete':
                result[str(op['entry']['id'])] = dict(deepcopy(op['entry']), _sync=op['state'])
        return month_entries(list(result.values()), month, identity)

    def peek_month(self, *args):
        return None

    def clear(self, kind=None):
        # Explicit reload expires network snapshots, never the durable outbox.
        self.last_refresh = 0

    def get_entry(self, business, entry_id):
        with self.lock:
            entry_id = self.data['aliases'].get(str(entry_id), str(entry_id))
            for op in self.data['outbox']:
                if str(op['business']) == str(business) and str(op['entry']['id']) == str(entry_id):
                    if op['kind'] == 'delete':
                        raise ApiError('This entry is waiting to be deleted.')
                    return dict(deepcopy(op['entry']), _sync=op['state'])
            for key, entries in self.data['months'].items():
                if key.split('/')[0] == str(business):
                    for entry in entries:
                        if str(entry['id']) == str(entry_id):
                            return deepcopy(entry)
            raise ApiError('Download this entry while online before editing it offline.')

    def _queue(self, kind, business, payload=None, original=None, identity=None):
        with self.lock:
            if not self.data.get('profile') or not self.connected:
                raise ApiError('Connect and download your account once before saving offline.')
            if self.message.startswith('This connection belongs'):
                raise ApiError(self.message)
            data = deepcopy(self.data)
            current = deepcopy(original)
            eid = str((original or {}).get('id', 'local-' + uuid.uuid4().hex))
            eid = data['aliases'].get(eid, eid)
            if current:
                current['id'] = eid
            op = next((o for o in data['outbox'] if str(o['business']) == str(business) and str(o['entry']['id']) == eid), None)
            if op and op['state'] not in ('queued', 'conflict'):
                raise ApiError('Check this uncertain change in Settings before changing it again.')
            owner = (payload or {}).get('time_entry', {}).get('identity_id', identity)
            if str(owner) != str(data['profile']['id']):
                raise ApiError('Only your own entries can be changed.')
            if original and (str(original.get('identity_id')) != str(owner) or edit_restriction(original)):
                raise ApiError('This entry cannot be changed here. Review it in FreshBooks.')
            if kind == 'create':
                current = dict(payload['time_entry'], id=eid, active=True)
                key = self._monthkey(business, entry_date(current).replace(day=1), owner)
                if key not in data['months']:
                    data['months'][key] = []
                    data['incomplete'].append(key)
            elif kind == 'update':
                current.update(payload['time_entry'])
                current['id'] = eid
            if kind == 'delete' and op and op['kind'] == 'create':
                data['outbox'].remove(op)
            else:
                if op:
                    if op['state'] == 'conflict':
                        raise ApiError('Resolve this conflict in Settings before editing it again.')
                    op.update(entry=current, payload=deepcopy(payload) if payload else op['payload'])
                    if kind == 'delete':
                        op['kind'] = 'delete'
                else:
                    if len(data['outbox']) >= 500:
                        raise ApiError('500 changes are waiting. Sync before adding more.')
                    base = deepcopy(original)
                    if base:
                        base['id'] = eid
                    data['outbox'].append(dict(qid=uuid.uuid4().hex, kind=kind, business=business,
                        entry=current, original=base, payload=deepcopy(payload), state='queued', error=''))
            self.persist(data)
            if kind == 'delete':
                return dict(deleted=True, id=eid, business_id=business, _queued=True)
            return dict(current, _sync='queued')

    def submit(self, business, payload):
        return self._queue('create', business, payload)

    def update_entry(self, business, entry_id, payload, original):
        if str(entry_id) != str(original.get('id')):
            raise ApiError('The selected entry does not match this edit.')
        return self._queue('update', business, payload, original)

    def delete_entry(self, business, entry_id, original, identity):
        if str(entry_id) != str(original.get('id')):
            raise ApiError('The selected entry does not match this deletion.')
        return self._queue('delete', business, original=original, identity=identity)

    @locked
    def _ack(self, op, entry=None):
        data = deepcopy(self.data)
        old_id = str(op['entry']['id'])
        for key, entries in data['months'].items():
            if key.split('/')[0] == str(op['business']):
                data['months'][key] = [e for e in entries if str(e['id']) not in (old_id, str((entry or {}).get('id')))]
                if entry:
                    _, identity, month = key.split('/')
                    if month_entries([entry], date.fromisoformat(month), identity):
                        data['months'][key].append(entry)
        if entry and old_id.startswith('local-'):
            data['aliases'][old_id] = str(entry['id'])
            while len(data['aliases']) > 500:
                data['aliases'].pop(next(iter(data['aliases'])))
        data['outbox'] = [o for o in data['outbox'] if o['qid'] != op['qid']]
        self.persist(data)

    @locked
    def _state(self, qid, state, error=''):
        data = deepcopy(self.data)
        next(o for o in data['outbox'] if o['qid'] == qid).update(state=state, error=error)
        self.persist(data)

    def _reconcile(self, op):
        pending = self.vault.get('pending')
        if not pending:
            # Successful provider writes record last_success atomically with
            # clearing pending. This closes the crash window before _ack.
            success = self.vault.get('last_success')
            if op['kind'] != 'delete' and success and success != op.get('before_success') and success.get('payload') == op['payload'] and str(success.get('business_id')) == str(op['business']):
                self._ack(op, self.backend.get_entry(op['business'], success['id']))
                return True
            if op['kind'] == 'delete':
                try:
                    current = self.backend.get_entry(op['business'], op['entry']['id'])
                except ApiError as exc:
                    if exc.status != 404:
                        raise
                    current = None
                if current is None or not current.get('active', True):
                    self._ack(op)
                    return True
            # No journal means no uncertain provider write remains. A crash
            # before dispatch can safely return this operation to the queue.
            if op['state'] == 'sending':
                self._state(op['qid'], 'queued')
            return False
        expected_kind = pending.get('operation', 'create')
        if str(pending.get('business_id')) != str(op['business']) or expected_kind != op['kind'] or (op['kind'] != 'delete' and pending.get('payload') != op['payload']) or (op['kind'] != 'create' and str(pending.get('entry_id')) != str(op['entry']['id'])):
            self._state(op['qid'], 'review', 'A previous submission needs verification before this change can sync.')
            return False
        if op['kind'] == 'create':
            # No idempotency key is documented: never replay this POST. A
            # matching row can be a separate intentionally identical entry.
            self._state(op['qid'], 'review', 'The connection dropped during submission. Check FreshBooks before retrying; the entry may already exist.')
            return False
        result = self.backend.check_pending()
        if result and not result.get('unresolved'):
            self._ack(op, None if result.get('deleted') else result)
            return True
        self._state(op['qid'], 'review', 'FreshBooks has not confirmed this change. Review it before retrying.')
        return False

    def sync(self, force=False):
        with self.sync_lock:
            if not self.connected or self.stopping.is_set():
                return 0
            actionable = any(o['state'] == 'sending' or (o['state'] == 'queued' and not self.vault.get('pending')) for o in self.data['outbox'])
            if not force and not actionable and time.monotonic() - self.last_refresh < 300:
                return 0
            if not self.probe():
                self.online = False
                return 0
            try:
                profile = self.backend.profile()
                self._identity(profile)
                self.online, self.message = True, ''
                count = 0
                for saved in list(self.data['outbox']):
                    if self.stopping.is_set():
                        return count
                    op = deepcopy(next((o for o in self.data['outbox'] if o['qid'] == saved['qid']), None))
                    if op is None:
                        continue
                    if op['state'] in ('sending', 'review'):
                        if self._reconcile(op):
                            count += 1
                        if any(o['qid'] == op['qid'] and o['state'] != 'queued' for o in self.data['outbox']):
                            continue
                        if not any(o['qid'] == op['qid'] for o in self.data['outbox']):
                            continue
                    if op['state'] == 'conflict':
                        continue
                    if self.vault.get('pending'):
                        self.message = 'Review the interrupted submission before syncing the remaining changes.'
                        break
                    with self.lock:
                        # Freeze only this operation before network preflight;
                        # unrelated local saves remain available during sync.
                        live = next((o for o in self.data['outbox'] if o['qid'] == op['qid']), None)
                        if live is None:
                            continue
                        data = deepcopy(self.data)
                        frozen = next(o for o in data['outbox'] if o['qid'] == live['qid'])
                        frozen.update(state='sending', before_success=deepcopy(self.vault.get('last_success')))
                        self.persist(data)
                        op = deepcopy(frozen)
                    if op['kind'] != 'create':
                        try:
                            current = self.backend.get_entry(op['business'], op['entry']['id'])
                        except ApiError as exc:
                            if exc.status == 404:
                                if op['kind'] == 'delete':
                                    self._ack(op); count += 1; continue
                                self._state(op['qid'], 'conflict', 'This entry was removed in FreshBooks. Your edit was retained locally.')
                                continue
                            raise
                        if op['kind'] == 'delete' and not current.get('active', True):
                            self._ack(op); count += 1; continue
                        if entry_signature(current) != entry_signature(op['original']):
                            self._state(op['qid'], 'conflict', 'This entry changed in FreshBooks. Your local change was not applied.')
                            continue
                    with self.lock:
                        data = deepcopy(self.data)
                        live = next(o for o in data['outbox'] if o['qid'] == op['qid'])
                        live.update(state='sending', before_success=deepcopy(self.vault.get('last_success')))
                        self.persist(data)
                        op = deepcopy(live)
                    try:
                        if op['kind'] == 'create':
                            entry = self.backend.submit(op['business'], op['payload'])
                        elif op['kind'] == 'update':
                            entry = self.backend.update_entry(op['business'], op['entry']['id'], op['payload'], op['original'])
                        else:
                            self.backend.delete_entry(op['business'], op['entry']['id'], op['original'], profile['id'])
                            entry = None
                        self._ack(op, entry)
                        count += 1
                    except ApiError as exc:
                        if self.vault.get('pending'):
                            self._state(op['qid'], 'review', 'Submission needs verification. No automatic retry will be made.')
                        else:
                            self._state(op['qid'], 'queued' if exc.uncertain or exc.status in (401, 429) else 'conflict', str(exc))
                        if exc.uncertain:
                            self.online = False
                            break
                # Refresh downloaded views only, never fetch an entire account's
                # history. Partial successes remain durable if a later read fails.
                if self.stopping.is_set():
                    return count
                catalogs, months = {}, {}
                for bid in list(self.data['catalogs']):
                    if self.stopping.is_set():
                        return count
                    business = next((m['business'] for m in profile.get('business_memberships', []) if str(m.get('business', {}).get('id')) == bid), None)
                    if business:
                        fresh = list(self.backend.catalog(business))
                        previous = self.data['catalogs'].get(bid)
                        if previous and fresh[3]:
                            if any(w.startswith('Projects unavailable:') for w in fresh[3]):
                                fresh[1] = previous[1]
                            if any(w.startswith('Services unavailable:') for w in fresh[3]):
                                fresh[2] = previous[2]
                        catalogs[bid] = fresh
                active = self.active_month
                if active in self.data['months']:
                    bid, identity, month = active.split('/')
                    months[active] = self.backend.entries_for_month(bid, date.fromisoformat(month), identity)
                with self.lock:
                    # Merge refreshed server snapshots into the latest outbox:
                    # local saves can arrive while these reads are in progress.
                    data = deepcopy(self.data)
                    data['profile'] = profile
                    data['catalogs'].update(catalogs)
                    data['months'].update(months)
                    data['incomplete'] = [key for key in data['incomplete'] if key not in months]
                    self.persist(data)
                self.last_refresh = time.monotonic()
                return count
            except ApiError as exc:
                self.message = str(exc)
                if exc.uncertain:
                    self.online = False
                return 0

    def resolve(self, qid, action):
        with self.lock:
            op = deepcopy(next((o for o in self.data['outbox'] if o['qid'] == qid), None))
            if not op:
                return
            if not self.probe():
                raise ApiError('Connect to review this change safely. It is still saved locally.')
            self._identity(self.backend.profile())
            # Review is an explicit, confirmed user decision. For an uncertain
            # POST no automated match or resend can prove the user's intention.
            if action == 'discard':
                data = deepcopy(self.data)
                data['outbox'] = [o for o in data['outbox'] if o['qid'] != qid]
                # Only release the provider journal belonging to this operation.
                pending = self.vault.get('pending')
                if pending:
                    owned = str(pending.get('business_id')) == str(op['business']) and pending.get('operation', 'create') == op['kind'] and ((op['kind'] == 'create' and pending.get('payload') == op['payload']) or (op['kind'] != 'create' and str(pending.get('entry_id')) == str(op['entry']['id'])))
                    if not owned:
                        raise ApiError('Resolve the earlier provider operation first.')
                    # Persist the user's discard before releasing its journal:
                    # a crash may retain a guard, never silently resend the POST.
                    self.persist(data)
                    self.vault.update(pending=None)
                else:
                    self.persist(data)
            else:
                raise ValueError('Use discard after reviewing FreshBooks, then edit or add the intended entry again.')
            self.last_refresh = 0

    def check_pending(self):
        if self.legacy_pending():
            return self.backend.check_pending()
        if self.data['outbox']:
            self.sync(force=True)
            return {'unresolved': True} if self.data['outbox'] else None
        return self.backend.check_pending()

    def connect(self, attempt, returned):
        with self.lock:
            old_client = (self.vault.get('credentials') or {}).get('client_id')
            new_client = attempt.credentials.get('client_id')
            if self.data['outbox'] and old_client != new_client:
                raise ApiError('Sync or review saved changes before switching developer applications.')
            self.backend.connect(attempt, returned)
            profile = self.backend.profile()
            if self.data['outbox'] or self.vault.get('pending'):
                self._identity(profile)
            else:
                self.persist(dict(profile=profile, catalogs={}, months={}, outbox=[], aliases={}, incomplete=[]))
            self.last_refresh = 0

    def disconnect(self):
        with self.lock:
            if self.data['outbox']:
                raise ApiError('Sync or review your locally saved changes before disconnecting.')
            self.backend.disconnect()
            self.persist(dict(profile=None, catalogs={}, months={}, outbox=[], aliases={}, incomplete=[]))

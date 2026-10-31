"""Real provider journaling against a deterministic fake HTTP server; no live writes."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs
import _paths
from freshtray.api import FreshBooks, ApiError
from freshtray.offline import OfflineAPI
from freshtray.model import entry_payload
from freshtray.storage import Vault
from test_core import MemoryVault, pair, CREDS


class Server:
    def __init__(self):
        self.rows, self.next_id, self.writes = {}, 100, []
        self.owner, self.fail = 99, None
    def __call__(self, method, path, body=None, token=None):
        url = urlsplit(path)
        if path == '/auth/api/v1/users/me':
            return {'response': {'id': self.owner, 'business_memberships': [{'role': 'owner', 'business': {'id': 1, 'account_id': 'a', 'name': 'Test'}}]}}
        if '/users/clients' in path:
            return {'response': {'result': {'clients': [{'id': 123, 'organization': 'Studio'}], 'pages': 1}}}
        if '/projects?' in path:
            return {'projects': [], 'meta': {'pages': 1}}
        if '/services?' in path:
            return {'services': [], 'meta': {'pages': 1}}
        if '/time_entries' in path:
            suffix = url.path.split('/time_entries', 1)[1].strip('/')
            if method == 'GET':
                if suffix:
                    row = self.rows.get(int(suffix))
                    if row is None:
                        raise ApiError('Gone', 404)
                    return {'time_entry': deepcopy(row)}
                return {'time_entries': deepcopy(list(self.rows.values())), 'meta': {'pages': 1}}
            self.writes.append(method)
            if self.fail == 'before':
                raise ApiError('Lost response', uncertain=True)
            if self.fail == 'rejected':
                raise ApiError('Invalid service', 422)
            if method == 'POST':
                self.next_id += 1
                result = dict(deepcopy(body['time_entry']), id=self.next_id, active=True)
                self.rows[self.next_id] = result
            elif method == 'PUT':
                result = self.rows[int(suffix)]
                result.update(deepcopy(body['time_entry']))
            else:
                self.rows.pop(int(suffix), None)
                result = {}
            if self.fail == 'after':
                raise ApiError('Lost response', uncertain=True)
            return {'time_entry': deepcopy(result)}
        raise AssertionError((method, path))


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault(tokens=pair(), credentials=CREDS)
        self.store = MemoryVault()
        self.server = Server()
        self.backend = FreshBooks(self.vault, self.server)
        self.network = True
        self.api = self.reopen()
        self.month = date.today().replace(day=1)
        self.payload = entry_payload(123, date.today().isoformat(), '2:00', 'Work', True, 99)
        self.api.profile(); self.api.catalog({'id': 1, 'account_id': 'a'})
        self.api.entries_for_month(1, self.month, 99)
    def reopen(self):
        return OfflineAPI(self.backend, self.vault, self.store, lambda: self.network)
    def existing(self):
        entry = self.backend.submit(1, self.payload)
        self.api.active_month = self.api._monthkey(1, self.month, 99)
        self.api.sync(force=True)
        self.server.writes.clear()
        return entry
    def rows(self):
        return self.api.entries_for_month(1, self.month, 99)
    def test_cached_restart_and_offline_add_survive(self):
        self.network = False
        local = self.api.submit(1, self.payload)
        self.api = self.reopen()
        self.assertEqual(self.api.profile()['id'], 99)
        self.assertEqual(self.api.catalog({'id': 1})[0][0]['id'], 123)
        self.assertEqual(self.rows()[0]['id'], local['id'])
        self.assertEqual(self.api.sync(), 0)
        self.assertEqual(self.server.writes, [])
        self.network = True
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(len(self.server.rows), 1)
        self.assertEqual(self.api.status()['count'], 0)
        self.assertFalse(str(self.rows()[0]['id']).startswith('local-'))
    def test_unsynced_edit_and_delete_cancel_without_network(self):
        self.network = False
        local = self.api.submit(1, self.payload)
        changed = deepcopy(self.payload); changed['time_entry']['note'] = 'Revised'
        self.api.update_entry(1, local['id'], changed, local)
        self.assertEqual(self.api.status()['count'], 1)
        self.assertEqual(self.rows()[0]['note'], 'Revised')
        self.api.delete_entry(1, local['id'], self.rows()[0], 99)
        self.assertEqual(self.api.status()['count'], 0)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.server.writes, [])
    def test_update_existing_then_delete_preserves_server_baseline(self):
        original = self.existing(); self.network = False
        changed = deepcopy(self.payload); changed['time_entry']['note'] = 'Local edit'
        self.api.update_entry(1, original['id'], changed, original)
        self.api.delete_entry(1, original['id'], self.rows()[0], 99)
        self.assertEqual(self.rows(), [])
        self.network = True
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.writes, ['DELETE'])
    def test_edit_existing_offline_then_sync(self):
        original = self.existing(); self.network = False
        changed = deepcopy(self.payload); changed['time_entry']['note'] = 'Local edit'
        self.api.update_entry(1, original['id'], changed, original)
        self.api = self.reopen()
        self.assertEqual(self.api.get_entry(1, original['id'])['note'], 'Local edit')
        self.network = True
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.rows[original['id']]['note'], 'Local edit')
    def test_conflict_does_not_overwrite_or_delete(self):
        for kind in ('update', 'delete'):
            with self.subTest(kind=kind):
                self.setUp(); original = self.existing()
                if kind == 'update':
                    self.api.update_entry(1, original['id'], self.payload, original)
                else:
                    self.api.delete_entry(1, original['id'], original, 99)
                self.server.rows[original['id']]['note'] = 'Changed elsewhere'
                self.api.sync()
                self.assertEqual(self.server.writes, [])
                self.assertEqual(self.api.status()['problems'][0]['status'], 'conflict')
                self.assertEqual(self.server.rows[original['id']]['note'], 'Changed elsewhere')
    def test_deleted_server_entry_satisfies_queued_delete(self):
        original = self.existing()
        self.api.delete_entry(1, original['id'], original, 99)
        self.server.rows.clear()
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.api.status()['count'], 0)
        self.assertEqual(self.server.writes, [])
    def test_deleted_server_entry_retains_local_edit_as_conflict(self):
        original = self.existing()
        self.api.update_entry(1, original['id'], self.payload, original)
        self.server.rows.clear(); self.api.sync()
        self.assertEqual(self.api.status()['problems'][0]['status'], 'conflict')
    def test_interrupted_create_is_never_automatically_replayed(self):
        for failure, expected in (('before', 0), ('after', 1)):
            with self.subTest(failure=failure):
                self.setUp(); self.api.submit(1, self.payload)
                self.server.fail = failure; self.api.sync()
                self.api = self.reopen(); self.server.fail = None
                self.api.sync(force=True); self.api.sync(force=True)
                self.assertEqual(self.server.writes, ['POST'])
                self.assertEqual(len(self.server.rows), expected)
                self.assertEqual(self.api.status()['problems'][0]['status'], 'review')
                self.assertIsNotNone(self.vault.get('pending'))
    def test_interrupted_update_reconciles_without_repeat(self):
        original = self.existing()
        changed = deepcopy(self.payload); changed['time_entry']['note'] = 'Changed'
        self.api.update_entry(1, original['id'], changed, original)
        self.server.fail = 'after'; self.api.sync()
        self.server.fail = None; self.api = self.reopen()
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.writes, ['PUT'])
        self.assertEqual(self.api.status()['count'], 0)
    def test_interrupted_delete_reconciles_without_repeat(self):
        original = self.existing()
        self.api.delete_entry(1, original['id'], original, 99)
        self.server.fail = 'after'; self.api.sync()
        self.server.fail = None; self.api = self.reopen()
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.writes, ['DELETE'])
    def test_crash_after_success_before_ack_uses_provider_journal(self):
        self.api.submit(1, self.payload)
        update = self.store.update
        def fail_ack(**values):
            if not values['offline_v1']['outbox']:
                raise OSError('disk unavailable')
            update(**values)
        self.store.update = fail_ack
        with self.assertRaises(OSError): self.api.sync()
        self.store.update = update; self.api = self.reopen()
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.writes, ['POST'])
    def test_crash_before_dispatch_can_resume(self):
        self.api.submit(1, self.payload)
        data = deepcopy(self.api.data)
        data['outbox'][0].update(state='sending', before_success=None)
        self.api.persist(data); self.api = self.reopen()
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.writes, ['POST'])
    def test_identical_intentional_creates_remain_distinct(self):
        self.api.submit(1, self.payload); self.api.submit(1, self.payload)
        self.assertEqual(self.api.sync(), 2)
        self.assertEqual(len(self.server.rows), 2)
    def test_other_account_never_receives_queued_changes(self):
        self.api.submit(1, self.payload); self.server.owner = 55
        self.assertEqual(self.api.sync(), 0)
        self.assertEqual(self.server.writes, [])
        self.assertIn('different FreshBooks account', self.api.status()['message'])
        with self.assertRaises(ApiError): self.api.submit(1, self.payload)
    def test_unknown_month_keeps_new_entry_across_success_and_restart(self):
        from freshtray.history_model import month_after
        month = month_after(self.month, -2)
        payload = entry_payload(123, month.isoformat(), '1:00', 'Older work', True, 99)
        self.network = False
        self.api.entries_for_month(1, month, 99)
        self.api.submit(1, payload)
        self.assertIn('only locally saved changes', self.api.status()['message'])
        self.network = True; self.api.sync()
        self.api = self.reopen(); self.network = False
        self.assertEqual(len(self.api.entries_for_month(1, month, 99)), 1)
    def test_uncached_account_cannot_work_offline(self):
        self.network = False
        api = OfflineAPI(self.backend, self.vault, MemoryVault(), lambda: False)
        with self.assertRaises(ApiError): api.profile()
        with self.assertRaises(ApiError): api.submit(1, self.payload)
    def test_storage_failure_does_not_claim_local_save(self):
        self.store.update = lambda **kw: (_ for _ in ()).throw(OSError('full'))
        with self.assertRaises(OSError): self.api.submit(1, self.payload)
        self.assertEqual(self.api.status()['count'], 0)
        self.assertEqual(self.server.writes, [])
    def test_disconnect_does_not_orphan_changes(self):
        self.api.submit(1, self.payload)
        with self.assertRaises(ApiError): self.api.disconnect()
    def test_explicit_review_discard_never_changes_server(self):
        self.api.submit(1, self.payload); self.server.fail = 'after'; self.api.sync()
        qid = self.api.status()['problems'][0]['id']
        self.server.fail = None
        self.api.resolve(qid, 'discard')
        self.assertEqual(self.api.status()['count'], 0)
        self.assertEqual(len(self.server.rows), 1)
        self.assertEqual(self.server.writes, ['POST'])
        self.assertIsNone(self.vault.get('pending'))
    def test_rejected_operation_is_visible_and_not_retried(self):
        self.api.submit(1, self.payload); self.server.fail = 'rejected'
        self.api.sync(); self.api.sync(force=True)
        self.assertEqual(self.api.status()['problems'][0]['status'], 'conflict')
        self.assertEqual(self.server.writes, ['POST'])
    def test_snapshot_and_outbox_are_dpapi_encrypted_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'offline.dpapi'
            api = OfflineAPI(self.backend, self.vault, Vault(path), lambda: True)
            api.profile(); api.submit(1, self.payload)
            self.assertNotIn(b'Work', path.read_bytes())
            self.assertNotIn(b'access', path.read_bytes())
            loaded = OfflineAPI(self.backend, self.vault, Vault(path), lambda: False)
            self.assertEqual(loaded.status()['count'], 1)

    def test_new_local_save_during_refresh_is_not_blocked_or_lost(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        old = self.backend.transport
        def held(method, path, *args, **kwargs):
            if path == '/auth/api/v1/users/me':
                entered.set()
                if not release.wait(3):
                    raise AssertionError('test synchronization timeout')
            return old(method, path, *args, **kwargs)
        self.backend.transport = held
        errors = []
        def sync():
            try: self.api.sync(force=True)
            except Exception as exc: errors.append(exc)
        worker = threading.Thread(target=sync); worker.start()
        self.assertTrue(entered.wait(1))
        try:
            self.api.submit(1, self.payload)
        finally:
            release.set(); worker.join(5)
        self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
        # It either synced in this pass or remains durably queued for the next.
        self.assertEqual(len(self.server.rows) + self.api.status()['count'], 1)
        self.api.sync(force=True)
        self.assertEqual(len(self.server.rows), 1)
    def test_uncertain_create_does_not_stall_later_changes_permanently(self):
        self.api.submit(1, self.payload)
        another = deepcopy(self.payload); another['time_entry']['note'] = 'Another'
        self.api.submit(1, another)
        self.server.fail = 'after'; self.api.sync()
        self.server.fail = None; self.api.sync(force=True)
        first = self.api.status()['problems'][0]['id']
        self.assertEqual(self.api.data['outbox'][1]['state'], 'queued')
        self.api.resolve(first, 'discard')
        self.api.sync(force=True)
        self.assertEqual(self.api.status()['count'], 0)
        self.assertEqual(len(self.server.rows), 2)
    def test_expired_refresh_is_not_consumed_while_offline(self):
        self.vault.get('tokens')['expires_at'] = 0
        self.network = False; self.api.submit(1, self.payload)
        self.api.sync()
        self.assertFalse(self.vault.get('refresh_inflight', False))
        self.assertEqual(self.api.status()['count'], 1)
    def test_synced_local_id_can_still_be_used_by_open_editor(self):
        local = self.api.submit(1, self.payload); self.api.sync()
        changed = deepcopy(self.payload); changed['time_entry']['note'] = 'Open draft'
        self.api.update_entry(1, local['id'], changed, local)
        self.api.sync()
        self.assertEqual(len(self.server.rows), 1)
        self.assertEqual(next(iter(self.server.rows.values()))['note'], 'Open draft')
    def test_review_creates_do_not_poll_the_api_constantly(self):
        self.api.submit(1, self.payload); self.server.fail = 'after'; self.api.sync()
        self.server.fail = None
        self.api.sync(force=True)
        def unexpected(*args, **kwargs): raise AssertionError('Unnecessary request')
        self.backend.transport = unexpected
        self.api.sync()

    def test_synced_local_id_can_be_deleted_by_open_editor(self):
        local = self.api.submit(1, self.payload); self.api.sync()
        self.api.delete_entry(1, local['id'], local, 99)
        self.assertEqual(self.api.sync(), 1)
        self.assertEqual(self.server.rows, {})
    def test_mismatched_entry_ids_are_rejected_locally(self):
        original = self.existing()
        with self.assertRaises(ApiError): self.api.update_entry(1, 999, self.payload, original)
        with self.assertRaises(ApiError): self.api.delete_entry(1, 999, original, 99)
        self.assertEqual(self.api.status()['count'], 0)

    def test_previous_build_pending_guard_stays_reviewable_with_new_queue(self):
        pending = {'business_id': 1, 'payload': deepcopy(self.payload)}
        self.vault.update(pending=pending)
        self.api.submit(1, self.payload)
        self.api.sync(force=True)
        self.assertTrue(self.api.legacy_pending())
        self.assertEqual(self.api.data['outbox'][0]['state'], 'queued')
        self.assertEqual(self.server.writes, [])
        self.assertTrue(self.api.check_pending()['unresolved'])
    def test_own_uncertain_guard_is_not_legacy(self):
        self.api.submit(1, self.payload)
        self.server.fail='after'; self.api.sync()
        self.assertFalse(self.api.legacy_pending())

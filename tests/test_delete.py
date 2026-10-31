import unittest
from copy import deepcopy
from unittest.mock import Mock
import _paths
from test_core import MemoryVault, pair, payload
from freshtray.api import FreshBooks, ApiError
from freshtray.read_cache import ReadCache

class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.entry=dict(payload()['time_entry'],id=7,active=True)
        self.vault=MemoryVault(tokens=pair())
        self.transport=Mock(return_value={})
        self.api=FreshBooks(self.vault,self.transport)
        self.api.get_entry=Mock(return_value=deepcopy(self.entry))
    def test_success_journals_and_sends_one_delete(self):
        def request(method,path,**kwargs):
            self.assertEqual(self.vault.get('pending')['operation'],'delete')
            self.assertEqual(method,'DELETE');self.assertTrue(path.endswith('/7'))
            return {}
        self.transport.side_effect=request
        result=self.api.delete_entry(1,7,self.entry,99)
        self.assertTrue(result['deleted']);self.assertIsNone(self.vault.get('pending'))
        self.assertEqual(self.transport.call_count,1)
    def test_changed_entry_or_wrong_identity_never_deletes(self):
        for updates in ({'note':'Changed elsewhere'},{'identity_id':100},{'id':8},{'active':False}):
            self.api.get_entry.return_value=dict(self.entry,**updates)
            with self.assertRaises(ApiError):self.api.delete_entry(1,7,self.entry,99)
        self.transport.assert_not_called()
    def test_mismatched_original_id_never_deletes(self):
        with self.assertRaises(ApiError):self.api.delete_entry(1,7,dict(self.entry,id=8),99)
        self.transport.assert_not_called()
    def test_pending_write_blocks_delete(self):
        self.vault.update(pending={'operation':'update'})
        with self.assertRaises(ApiError):self.api.delete_entry(1,7,self.entry,99)
        self.transport.assert_not_called()
    def test_definitive_failure_clears_guard(self):
        self.transport.side_effect=ApiError('Denied',403)
        with self.assertRaises(ApiError):self.api.delete_entry(1,7,self.entry,99)
        self.assertIsNone(self.vault.get('pending'))
    def test_uncertain_delete_404_reconciliation_never_retries(self):
        self.transport.side_effect=ApiError('Interrupted',uncertain=True)
        with self.assertRaises(ApiError):self.api.delete_entry(1,7,self.entry,99)
        self.assertEqual(self.vault.get('pending')['operation'],'delete')
        self.api.get_entry.side_effect=ApiError('Missing',404)
        self.assertTrue(self.api.check_pending()['deleted'])
        self.assertIsNone(self.vault.get('pending'));self.assertEqual(self.transport.call_count,1)
    def test_active_unresolved_and_deleted_reconciliation(self):
        self.vault.update(pending={'operation':'delete','business_id':1,'entry_id':7,'payload':{'time_entry':self.entry}})
        self.assertTrue(self.api.check_pending()['unresolved'])
        self.assertIsNotNone(self.vault.get('pending'))
        self.api.get_entry.return_value=dict(self.entry,active=False)
        self.assertTrue(self.api.check_pending()['deleted'])
        self.assertIsNone(self.vault.get('pending'))
    def test_delete_invalidates_month_cache(self):
        backend=Mock();cache=ReadCache(backend)
        backend.entries_for_month.return_value=[self.entry]
        from datetime import date
        month=date.today().replace(day=1)
        cache.entries_for_month(1,month,99);cache.delete_entry(1,7,self.entry,99)
        cache.entries_for_month(1,month,99)
        self.assertEqual(backend.entries_for_month.call_count,2)

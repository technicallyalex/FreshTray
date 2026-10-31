import unittest
from unittest.mock import Mock,patch
from datetime import date
import _paths
from freshtray.read_cache import ReadCache

class ReadCacheTests(unittest.TestCase):
    def setUp(self):
        self.backend=Mock()
        self.backend.profile.return_value={'id':42}
        self.backend.catalog.return_value=([{'id':1}],[],[],[])
        self.backend.entries_for_month.return_value=[{'id':1,'note':'Original'}]
        self.cache=ReadCache(self.backend)
        self.month=date(2026,1,1)
    def test_repeated_month_uses_one_call_and_defensive_copy(self):
        first=self.cache.entries_for_month(1,self.month,42);first[0]['note']='Draft'
        self.assertEqual(self.cache.entries_for_month(1,self.month,42)[0]['note'],'Original')
        self.backend.entries_for_month.assert_called_once()
    def test_business_identity_month_are_isolated(self):
        for bid,month,identity in [(1,self.month,42),(2,self.month,42),(1,self.month,43),(1,date(2026,2,1),42)]:
            self.cache.entries_for_month(bid,month,identity)
        self.assertEqual(self.backend.entries_for_month.call_count,4)
    def test_expiry_fetches_again(self):
        with patch('freshtray.read_cache.time.monotonic',return_value=100):self.cache.profile()
        with patch('freshtray.read_cache.time.monotonic',return_value=701):self.cache.profile()
        self.assertEqual(self.backend.profile.call_count,2)
    def test_failed_read_is_not_cached(self):
        self.backend.profile.side_effect=ValueError('offline')
        for _ in range(2):
            with self.assertRaises(ValueError):self.cache.profile()
        self.assertEqual(self.backend.profile.call_count,2)
    def test_explicit_clear_reloads(self):
        self.cache.entries_for_month(1,self.month,42);self.cache.clear('month')
        self.cache.entries_for_month(1,self.month,42)
        self.assertEqual(self.backend.entries_for_month.call_count,2)
    def test_write_invalidates_even_if_interrupted(self):
        self.cache.entries_for_month(1,self.month,42)
        self.backend.submit.side_effect=ValueError('interrupted')
        with self.assertRaises(ValueError):self.cache.submit(1,{})
        self.cache.entries_for_month(1,self.month,42)
        self.assertEqual(self.backend.entries_for_month.call_count,2)
    def test_identity_change_clears_everything(self):
        self.cache.profile();self.cache.connect({},'url');self.cache.profile()
        self.assertEqual(self.backend.profile.call_count,2)
    def test_cache_is_bounded(self):
        for i in range(50):self.cache.entries_for_month(i,self.month,42)
        self.assertLessEqual(len(self.cache.items),32)

from datetime import datetime,timedelta,timezone
import unittest
import _paths
from freshtray.reminder_delay import ReminderDelay,delay_minutes
class Prefs:
    def __init__(self):self.data={'time':'17:00','last_reminded':'2026-10-31'}
    def save(self,**values):self.data.update(values)
class DelayTests(unittest.TestCase):
    def setUp(self):
        self.prefs=Prefs();self.now=datetime(2026,10,31,18,tzinfo=timezone.utc)
        self.delay=ReminderDelay(self.prefs,lambda:self.now)
    def test_restores_deadline_and_delivers_once(self):
        self.delay.schedule(15)
        restored=ReminderDelay(self.prefs,lambda:self.now)
        self.assertEqual(restored.remaining(),900)
        self.assertFalse(restored.consume())
        self.now+=timedelta(minutes=15)
        self.assertTrue(restored.consume());self.assertFalse(restored.consume())
        self.assertIsNone(self.prefs.data['reminder_again_at'])
        self.assertEqual(self.prefs.data['time'],'17:00')
        self.assertEqual(self.prefs.data['last_reminded'],'2026-10-31')
    def test_overdue_after_sleep_is_delivered(self):
        self.delay.schedule(5);self.now+=timedelta(hours=2)
        self.assertTrue(self.delay.consume())
    def test_pressing_again_replaces_deadline(self):
        self.delay.schedule(5);self.now+=timedelta(minutes=2);self.delay.schedule(10)
        self.assertEqual(self.delay.remaining(),600)
    def test_invalid_delay_and_corrupt_deadline(self):
        for value in (0,-1,1441,1.5,True,'bad',None):
            with self.assertRaises(ValueError):delay_minutes(value)
        for value in ('bad','2026-10-31T17:00:00',None):
            self.prefs.data['reminder_again_at']=value
            self.assertIsNone(self.delay.remaining())
    def test_clock_moves_backward_without_early_delivery(self):
        self.delay.schedule(10);self.now-=timedelta(hours=1)
        self.assertEqual(self.delay.remaining(),4200);self.assertFalse(self.delay.consume())

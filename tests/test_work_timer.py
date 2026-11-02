"""Failure and recovery checks for durable timers without live account data."""
import unittest
from copy import deepcopy
from unittest.mock import patch
import _paths
from PySide6.QtCore import QObject,Signal,QCoreApplication
from freshtray.work_timer import WorkTimer
from test_core import MemoryVault

app=QCoreApplication.instance() or QCoreApplication([])
class Prefs:
    data={}
    def save(self,**values):self.data=dict(self.data,**values)
class Owner(QObject):
    error=Signal(str)
    def __init__(self,saved=None):
        super().__init__();self.vault=MemoryVault(work_timer=saved);self.prefs=Prefs();self.offline=None
        self.forms={'timer':dict(client='1',project='',service='',day='2026-11-02',hours='8:00',note='',billable=True)}
        self._s={'catalogReady':True,'busy':False};self.business={'id':1};self.profile={'id':99};self.errors=[];self.error.connect(self.errors.append)
    def reset_form(self,scope):self.forms[scope].update(note='')
    def emit(self):pass
    def confirm(self,*args):pass
class WorkTimerTests(unittest.TestCase):
    def make(self,saved=None):
        owner=Owner(saved);timer=WorkTimer(owner)
        self.addCleanup(timer.ui.stop);self.addCleanup(timer.checkpoint.stop);self.addCleanup(timer.draft_save.stop)
        return owner,timer
    def test_failed_initial_checkpoint_does_not_start(self):
        owner,timer=self.make()
        with patch.object(owner.vault,'update',side_effect=OSError('disk')):timer.primary()
        self.assertEqual(timer.status,'idle');self.assertEqual(timer.elapsed(),0);self.assertTrue(owner.errors)
    def test_invalid_review_duration_cannot_submit_old_value(self):
        owner,timer=self.make();timer.status='review';timer.seconds=90
        timer.duration('00:99:00');self.assertFalse(timer.state['durationValid'])
        timer.save_entry();self.assertEqual(timer.seconds,90);self.assertIsNone(timer.submission)
        timer.duration('00:02:00');self.assertTrue(timer.state['durationValid']);self.assertEqual(timer.seconds,120)
    def test_bad_optional_saved_preferences_are_safe(self):
        owner,timer=self.make({'seconds':'bad','status':'paused','form':{'note':None,'client':[]}})
        owner.prefs.data={'timer_opacity':'bad','timer_face':'removed','timer_position':{'x':'bad','y':0}}
        self.assertEqual(timer.state['opacity'],1);self.assertEqual(timer.state['face'],'digital')
        self.assertEqual(timer.savedPosition,{});self.assertEqual(owner.forms['timer']['note'],'')
    def test_interruption_before_queue_allows_reviewed_retry(self):
        owner,timer=self.make();timer.status='review';timer.seconds=90;timer.submission={'time_entry':{}};timer.request_id='token'
        class Offline:
            def timer_submission_state(self,request):return 'absent'
        owner.offline=Offline();timer.recover_submission()
        self.assertEqual(timer.status,'review');self.assertEqual(timer.seconds,90);self.assertIsNone(timer.submission)
    def test_failed_clear_retains_saved_submission_guard(self):
        owner,timer=self.make();timer.status='review';timer.seconds=90;timer.submission={'time_entry':{}};timer.request_id='token'
        with patch.object(owner.vault,'update',side_effect=OSError('disk')):self.assertFalse(timer.clear())
        self.assertEqual(timer.status,'review');self.assertEqual(timer.seconds,90);self.assertIsNotNone(timer.submission)
if __name__=='__main__':unittest.main()

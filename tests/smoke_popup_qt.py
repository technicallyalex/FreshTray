"""Independent reminder window checks; never changes Windows notification settings.

Use QT_QPA_PLATFORM=windows for a native-window pass on Windows.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QUrl,QObject,Qt,QEvent,QCoreApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault,Preferences

root=Path(__file__).resolve().parents[1]
app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
def pump(seconds=.4):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.005)
class BlockedTray:
    def __init__(self,fail=False):self.fail=fail;self.calls=0
    def showMessage(self,*args):
        self.calls+=1
        if self.fail:raise RuntimeError('Simulated unavailable notification service')
with tempfile.TemporaryDirectory(prefix='FreshTray-Popup-QA-') as d,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(d);prefs=Preferences(folder/'settings.json')
    prefs.save(reminders=False,popup_sound=False,reminder_popup=True)
    b=Controller(Demo(),Vault(folder/'vault.dpapi'),prefs,root/'src/assets',root/'src/main.pyw',True,tray=False)
    b.reminder_timer.stop();b.sync_timer.stop();b.delay_timer.stop()
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b)
    e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects()
    w=e.rootObjects()[0];b.window=w;pump();w.hide()
    reminder=w.findChild(QObject,'reminderWindow')
    for failed in (False,True):
        tray=BlockedTray(failed);b.tray=tray
        b.testReminder();pump()
        assert reminder.isVisible() and reminder.opacity()==1
        assert reminder.flags() & Qt.WindowStaysOnTopHint
        assert not w.isVisible() and tray.calls==1
        reminder.hide();pump(.03)
        prefs.save(reminders=True,time='00:00',weekdays_only=False,last_reminded='')
        b.last_delivered='';b.tick();pump()
        assert reminder.isVisible() and tray.calls==2
        reminder.hide();b.tick();pump(.03)
        assert not reminder.isVisible() and tray.calls==2,'Daily reminder duplicated'
        prefs.save(reminders=False,reminder_popup=False)
        b.delayed_reminder.now=lambda:datetime.now(timezone.utc)
        assert b.remindMe()
        b.delayed_reminder.now=lambda:datetime.now(timezone.utc)+timedelta(days=2)
        assert b.deliver_delayed_reminder();pump()
        assert reminder.isVisible() and b.reminder_is_followup
        reminder.hide();prefs.save(reminder_popup=True)
    b.tray=None;b.timer.stop();b.delay_timer.stop();b.popup_chime.close()
    b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS: test, scheduled and snoozed popup windows survive suppressed and failed toast delivery; no Windows settings changed.')

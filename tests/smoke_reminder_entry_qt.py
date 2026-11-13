"""Single-use reminder form with isolated data and fake FreshBooks transport."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl,QObject,QMetaObject,Qt,QCoreApplication,QEvent,qInstallMessageHandler,QPointF
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuick import QQuickItem
from freshtray.api import FreshBooks
from freshtray.qt_app import Controller
from freshtray.storage import Vault,Preferences
from test_offline import Server
from test_core import pair,CREDS
app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
root=Path(__file__).resolve().parents[1]
for font in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
messages=[];qInstallMessageHandler(lambda kind,ctx,msg:messages.append(msg))
def pump(seconds=.08):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.003)
def settle(b):
    until=time.monotonic()+8
    while b.state['busy'] or b.syncing:
        pump(.01)
        assert time.monotonic()<until,'operation did not settle'
    pump(.08)
def click(parent,name):
    button=parent.findChild(QObject,name);assert button is not None,name
    QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
with tempfile.TemporaryDirectory() as d,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(d);v=Vault(folder/'vault.dpapi');v.update(credentials=CREDS,tokens=pair())
    p=Preferences(folder/'settings.json');p.save(reminders=False,popup_sound=False,theme="light")
    provider=FreshBooks(v,Server());b=Controller(provider,v,p,root/'src/assets',root/'src/main.pyw',False,tray=False)
    b.offline.probe=lambda:True;b.sync_timer.stop();b.reminder_timer.stop()
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b);e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),messages
    w=e.rootObjects()[0];b.window=w;b.start();settle(b);w.hide()
    b.setField('log','note','Keep my main-window draft')
    reminder=w.findChild(QObject,'reminderWindow')
    b.testReminder();pump();click(reminder,'reminderLog');pump()
    assert reminder.isVisible() and reminder.property('logging') and not w.isVisible()
    assert b.forms['log']['note']=='Keep my main-window draft'
    reminder.grabWindow().save(str(root/'.build/reminder-entry.png'))
    # Date picking must belong to this popup, not the hidden main window.
    picker=reminder.findChild(QObject,'reminderPicker')
    QMetaObject.invokeMethod(picker,'open',Qt.DirectConnection);pump()
    assert picker.property('visible') and not w.isVisible()
    QMetaObject.invokeMethod(picker,'close',Qt.DirectConnection)
    # The form stays usable on short desktops through local overflow scrolling.
    reminder.setHeight(510);b.applySetting('theme','dark');pump()
    reminder.grabWindow().save(str(root/'.build/reminder-entry-short-dark.png'))
    scroll=reminder.findChild(QObject,'reminderEntryScroll')
    flick=scroll.property('contentItem')
    assert flick.property('contentHeight')>flick.height()
    flick.setProperty('contentY',flick.property('contentHeight')-flick.height());pump()
    save=reminder.findChild(QQuickItem,'reminderSave')
    position=save.mapToScene(QPointF(0,0))
    assert position.y()>=0 and position.y()+save.height()<=reminder.height(), 'Log time must be reachable on short desktops'
    flick.setProperty('contentY',0)
    reminder.setHeight(650);b.applySetting('theme','light');pump()
    b.setField('reminder','hours','invalid')
    click(reminder,'reminderSave');pump()
    assert reminder.isVisible() and reminder.property('problem'), 'Validation must remain inside popup'
    b.setField('reminder','client','123');b.setField('reminder','hours','0:30');b.setField('reminder','note','Reminder QA')
    # Disk failure must preserve the draft and prevent a false confirmation/close.
    with patch.object(b.offline,'persist',side_effect=OSError('Synthetic disk failure')):
        click(reminder,'reminderSave');settle(b)
    assert reminder.isVisible() and not reminder.property('completed') and b.forms['reminder']['note']=='Reminder QA'
    # Success syncs immediately, confirms once and never opens/hides the main app.
    click(reminder,'reminderSave');settle(b)
    assert reminder.property('completed') and reminder.isVisible() and not w.isVisible()
    assert 'Entry saved' in reminder.property('feedback')
    assert len(provider.transport.rows)==1 and not b.offline.status()['count']
    pump(1.5);assert not reminder.isVisible() and not w.isVisible()
    assert b.forms['log']['note']=='Keep my main-window draft'
    # Reopening gives a fresh one-use form. Offline success is durable and honest.
    b.testReminder();pump();click(reminder,'reminderLog');pump()
    assert not reminder.property('completed') and b.forms['reminder']['note']==''
    b.offline.probe=lambda:False
    b.setField('reminder','client','123');b.setField('reminder','hours','0:15');b.setField('reminder','note','Offline reminder QA')
    click(reminder,'reminderSave');settle(b)
    assert reminder.property('completed') and b.offline.status()['count']==1
    assert 'saved locally' in reminder.property('feedback'),reminder.property('feedback')
    pump(1.5);assert not reminder.isVisible()
    b.offline.probe=lambda:True;b.syncNow();settle(b);assert len(provider.transport.rows)==2
    # Cancel does not save or alter the main draft.
    b.testReminder();pump();click(reminder,'reminderLog');pump();b.setField('reminder','note','Discard this');click(reminder,'reminderEntryCancel');pump()
    assert not reminder.isVisible() and len(provider.transport.rows)==2 and b.forms['reminder']['note']==''
    assert b.forms['log']['note']=='Keep my main-window draft'
    # Duplicate protection opens in the popup and rejection does not close it.
    b.testReminder();pump();click(reminder,'reminderLog');pump()
    b.setField('reminder','client','123');b.setField('reminder','hours','0:15');b.setField('reminder','note','Offline reminder QA')
    click(reminder,'reminderSave');pump()
    confirmation=w.findChild(QObject,'confirmDialog')
    assert confirmation.property('visible') and not w.isVisible()
    QMetaObject.invokeMethod(confirmation,'reject',Qt.DirectConnection);pump()
    assert reminder.isVisible() and not reminder.property('completed') and len(provider.transport.rows)==2
    # Closing while duplicate confirmation is open must cancel its pending action.
    click(reminder,'reminderSave');pump()
    assert confirmation.property('visible')
    reminder.hide();pump()
    assert b.pending_action is None and len(provider.transport.rows)==2
    assert not [m for m in messages if 'ReferenceError' in m or 'TypeError' in m or 'Binding loop' in m],messages
    b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close()
    b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS: one-use reminder form, isolated draft, validation/disk failure, online/offline save, confirmation, auto-close, cancel and immediate sync; no live writes.')

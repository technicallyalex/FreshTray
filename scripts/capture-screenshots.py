"""Capture maintained documentation images using isolated, fictional data only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QUrl,QObject,QCoreApplication,QEvent,Property
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault,Preferences
from freshtray.model import entry_payload
root=Path(__file__).resolve().parents[1];output=root/'docs/images';output.mkdir(exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
for font in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
def pump(seconds=.4):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.005)
def settle(b):
    until=time.monotonic()+8
    while b.state['busy'] and time.monotonic()<until:pump(.02)
    assert not b.state['busy'];pump(.5)
class ScreenshotController(Controller):
    @Property(bool,constant=True)
    def reducedMotion(self):return True
with tempfile.TemporaryDirectory(prefix='FreshTray-Docs-') as d,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(d);prefs=Preferences(folder/'settings.json');prefs.save(reminders=False,popup_sound=True,theme='light')
    provider=Demo();provider.entries={}
    for day in (1,2,5,6,7,8,9,12,13,14,15,16,19,20,21,22,23,26,27,28,29,30):
        provider.submit(1,entry_payload(1,date(2026,10,day).isoformat(),'8:00','Editing and project planning',True,42,1,1))
    b=ScreenshotController(provider,Vault(folder/'vault.dpapi'),prefs,root/'src/assets',root/'src/main.pyw',True,tray=False)
    b.screen_geometry=lambda:dict(x=0,y=0,width=1600,height=1000)
    b.reminder_timer.stop();b.sync_timer.stop();b.delay_timer.stop()
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b)
    e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects();w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b)
    b.setField('log','note','Editing and project planning');b.setField('log','hours','8:00');settle(b)
    assert w.grabWindow().save(str(output/'log-time.png'))
    b.selectPanel('month');settle(b);b.chooseMonth(2026,10);settle(b);b.selectDay('2026-10-29');settle(b)
    assert w.grabWindow().save(str(output/'monthly-hours.png'))
    b.applySetting('theme','dark');pump(.5)
    assert w.grabWindow().save(str(output/'monthly-hours-dark.png'))
    b.applySetting('theme','light');b.connectionSection(False);b.selectPanel('settings');settle(b)
    assert w.grabWindow().save(str(output/'settings.png'))
    b.testReminder();pump(.5);reminder=w.findChild(QObject,'reminderWindow')
    assert reminder.grabWindow().save(str(output/'reminder.png'));reminder.hide()
    b.timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('Saved five screenshots from fictional data; no account profile or network access used.')

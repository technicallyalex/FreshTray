"""Invoice/wizard layouts and input focus with synthetic records only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','windows')
import sys,time,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QObject,QUrl,QPointF,QCoreApplication,QEvent,QMetaObject,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtGui import QFontDatabase
from freshtray.qt_app import Controller
from freshtray.api import FreshBooks
from freshtray.storage import Vault,Preferences
from freshtray.local_provider import LocalProvider
from freshtray.model import entry_payload
from datetime import date
root=Path(__file__).resolve().parents[1];app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
for p in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(p))
messages=[];qInstallMessageHandler(lambda kind,ctx,msg:messages.append(msg))
def pump(seconds=.2):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);time.sleep(.003)
def settle(b):
    until=time.monotonic()+6
    while b.state['busy']:pump(.02);assert time.monotonic()<until
    pump(.4)
class AuditController(Controller):
    def windowBounds(self):return dict(x=0,y=0,width=2560,height=1440)
with tempfile.TemporaryDirectory() as folder,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(folder);v=Vault(folder/'vault.dpapi');p=Preferences(folder/'settings.json');p.save(standalone=True,reminders=False)
    b=AuditController(FreshBooks(v),v,p,root/'src/assets',root/'src/main.pyw',False,tray=False)
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b);e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),messages
    w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b);bill=b.invoices
    bill.seller(dict(name='Example Studio',email='studio@example.invalid',address='Example address',currency='USD'))
    bill.addRecord('clients',dict(name='Example Client',email='client@example.invalid'))
    settle(b);cid=str(bill.state['clients'][0]['id'])
    LocalProvider(v).submit(-1001,entry_payload(cid,date.today().isoformat(),'2:00','Example work',True,-1001))



    import faulthandler
    faulthandler.dump_traceback_later(50,exit=True)
    b.selectPanel('settings');b.connectionSection(True);pump(1)
    changes=[];w.heightChanged.connect(lambda:changes.append(time.monotonic()))
    refit=w.findChild(QObject,'settingsRefitTimer');busy_samples=0;total=0;start=time.monotonic()
    while time.monotonic()-start<6:
        pump(.1);total+=1
        busy_samples+=bool(w.property('animating') or refit.property('running'))
    print('IDLE QUIET',dict(height_changes=len(changes),refit_samples=busy_samples,total=total,animating=w.property('animating'),refit=refit.property('running'),center=w.property('centerResize')),flush=True)
    assert len(changes)<5 and busy_samples<5,'Idle layout keeps resizing'
    faulthandler.cancel_dump_traceback_later()
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS connection-panel idle soak',flush=True)

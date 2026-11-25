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



    pump(.5)
    assert abs(w.x()-(2560-w.width())/2)<=2 and abs(w.y()-(1440-w.height())/2)<=2,(w.x(),w.y(),w.width(),w.height())
    w.setX(480);w.setY(260);pump(.6)
    stored=Preferences(folder/'settings.json').data['window_position'];assert stored==dict(x=480,y=260),stored
    w.hide();w.setX(0);w.setY(0);w.setProperty('positionReady',False);w.show();pump(.5)
    assert w.x()==480 and w.y()==260,(w.x(),w.y())
    b.prefs.save(window_position=dict(x=999999,y=999999))
    placement=b.initialWindowPlacement(int(w.width()),int(w.height()))
    assert placement['x']>=0 and placement['y']>=0 and placement['x']+w.width()<=2560 and placement['y']+w.height()<=1440
    b.prefs.save(window_position=None)
    placement=b.initialWindowPlacement(720,660);assert placement['x']==920 and placement['y']==390,placement
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS first-show centered, position saved after move, restored on reopening, offscreen clamp and fresh-launch center',flush=True)

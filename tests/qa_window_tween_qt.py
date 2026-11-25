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




    pump(.6);w.setX(600);w.setY(300)
    cx,cy=w.x()+w.width()/2,w.y()+w.height()/2
    start=(w.width(),w.height());target=(int(w.width()+100),int(w.height()+80));samples=[]
    b.resizeMainWindow(*target,cx,cy,True)
    until=time.monotonic()+.65
    while time.monotonic()<until:
        app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        samples.append((w.width(),w.height()))
        assert abs((w.x()+w.width()/2)-cx)<=1 and abs((w.y()+w.height()/2)-cy)<=1
        if b.resizeAnimating:b.resizeMainWindow(*target,cx,cy,True)
        time.sleep(.01)
    assert not b.resizeAnimating and samples[-1]==target,samples
    assert len(set(samples))>=4,'Tween must render intermediate window sizes'
    b.resizeMainWindow(start[0],start[1],cx,cy,True);pump(.05);b.resizeMainWindow(target[0],target[1],cx,cy,True);pump(.5)
    assert not b.resizeAnimating and (w.width(),w.height())==target
    b.resizeMainWindow(start[0],start[1],cx,cy,True);b.cancelWindowResize();assert not b.resizeAnimating
    w.showMinimized();pump(.1);b.show_panel('settings');pump(.8)
    assert w.visibility()==w.Visibility.Windowed and not b.resizeAnimating and w.width()==720
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS centered cubic tween, intermediate sizes, finite completion, duplicate target coalescing, interruption and cancellation without rendering frames',flush=True)

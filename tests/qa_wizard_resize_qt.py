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
    # Every automatic panel resize must preserve its previous center.
    b.selectPanel('settings');pump(.5);w.setX(800);w.setY(320)
    for page in ['log','month','timer','invoices','settings']:
        before=(w.x()+w.width()/2,w.y()+w.height()/2)
        b.selectPanel(page);pump(.55)
        after=(w.x()+w.width()/2,w.y()+w.height()/2)
        print('CENTER',page,before,after,flush=True)
        assert abs(before[0]-after[0])<=2 and abs(before[1]-after[1])<=2,(page,before,after)
    before=(w.x()+w.width()/2,w.y()+w.height()/2)
    b.connectionSection(True);pump(.5)
    assert abs(before[0]-(w.x()+w.width()/2))<=2 and abs(before[1]-(w.y()+w.height()/2))<=2
    wizard=w.findChild(QObject,'setupWizard')
    for width,height in [(560,490),(720,540),(1220,980)]:
        for theme in ['light','dark']:
            b.applySetting('theme',theme);pump(.1);w.setWidth(width);w.setHeight(height);pump(.4)
            print('OPEN',width,height,theme,flush=True)
            QMetaObject.invokeMethod(wizard,'open',Qt.DirectConnection);pump(.15)
            for step in range(4):
                wizard.setProperty('step',step);pump(.12)
                assert wizard.property('width')<=w.width() and wizard.property('height')<=w.height()
            QMetaObject.invokeMethod(wizard,'close',Qt.DirectConnection);pump(.15)
    # A simulated browser launch stays responsive; closing cancels and clears fields.
    QMetaObject.invokeMethod(wizard,'open',Qt.DirectConnection);wizard.setProperty('step',2);pump(.1)
    with patch('freshtray.qt_app.QDesktopServices.openUrl',return_value=True):
        b.beginBillingConnect('synthetic-client','synthetic-secret','https://localhost:8765/callback')
    assert b.state['authStarted']
    wizard.findChild(QObject,'setupClientSecret').setProperty('text','synthetic-secret')
    wizard.findChild(QObject,'setupReturnUrl').setProperty('text','https://localhost:8765/callback?synthetic')
    QMetaObject.invokeMethod(wizard,'close',Qt.DirectConnection);pump(.15)
    assert not b.state['authStarted']
    assert wizard.findChild(QObject,'setupClientSecret') is None or not wizard.findChild(QObject,'setupClientSecret').property('text')
    assert wizard.findChild(QObject,'setupReturnUrl') is None or not wizard.findChild(QObject,'setupReturnUrl').property('text')
    # Mode control belongs to Settings; switching preserves local records.
    from PySide6.QtTest import QTest
    toggle=w.findChild(QQuickItem,'standaloneToggle')
    assert toggle and toggle.property('checked')
    point=toggle.mapToScene(QPointF(toggle.width()/2,toggle.height()/2)).toPoint()
    QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point);pump(.5)
    assert not b.local_mode and not toggle.property('checked') and b.state['panel']=='settings'
    point=toggle.mapToScene(QPointF(toggle.width()/2,toggle.height()/2)).toPoint()
    QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point);settle(b)
    assert b.local_mode and toggle.property('checked') and b.state['panel']=='settings'
    assert bill.store.data()['clients'][0]['name']=='Example Client'
    assert not [item for item in w.findChildren(QQuickItem) if item.property('text')=='Setup wizard']
    # Near an edge, fitting is allowed to shift the center to keep the full window visible.
    w.setX(0);w.setY(0);b.selectPanel('invoices');pump(.5)
    assert w.x()>=0 and w.y()>=0 and w.x()+w.width()<=2560 and w.y()+w.height()<=1440
    errors=[m for m in messages if any(t in m for t in ('ReferenceError','TypeError','Binding loop','is not defined','polish loop','recursive rearrange'))]
    assert not errors,errors
    faulthandler.cancel_dump_traceback_later()
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS native wizard steps at three sizes in both themes; centered panel resizing; no layout loops',flush=True)

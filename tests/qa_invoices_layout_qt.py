"""Invoice/wizard layouts and input focus with synthetic records only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
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
    def windowBounds(self):return dict(x=0,y=0,width=1280,height=900)
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
    cases=0
    for width,height in [(1040,760),(620,540)]:
        for theme in ['light','dark']:
            b.applySetting('theme',theme);pump();w.setWidth(width);w.setHeight(height);pump(.3)
            bill.newInvoice();bill.field('client',cid);bill.line(0,'name','Service');bill.line(0,'rate','125');bill.line(0,'description',('Editing service / long multiline historical invoice\nSecond line of notes\n'*25));bill.save();pump()
            for view in ['list','edit','import','preview']:
                if view=='list':bill.back()
                if view=='edit':bill.openInvoice(bill.state['rows'][0]['id'])
                if view=='import':bill.openImport();bill.importField('rate','100')
                if view=='preview':bill.editPreview();bill.showPreview()
                pump()
                panel=w.findChild(QQuickItem,'invoicesPanel');pos=panel.mapToScene(QPointF(0,0))
                assert pos.x()>=-1 and pos.x()+panel.width()<=w.width()+1
                assert pos.y()>=-1 and pos.y()+panel.height()<=w.height()+1
                if view=='list':
                    assert all('\n' not in r['description'] and len(r['description'])<=400 for r in bill.state['rows'])
                if width==1040:w.grabWindow().save(str(root/'.build'/('invoice-'+view+'-'+theme+'.png')))
                cases+=1
            bill.editPreview()
            wizard=w.findChild(QObject,'setupWizard');QMetaObject.invokeMethod(wizard,'open',Qt.DirectConnection);pump()
            for step in range(4):
                wizard.setProperty('step',step);pump(.08)
                assert wizard.property('width')<=w.width() and wizard.property('height')<=w.height()
                if width==1040 and theme=='light':w.grabWindow().save(str(root/'.build'/('setup-step-'+str(step)+'.png')))
                cases+=1
            QMetaObject.invokeMethod(wizard,'close',Qt.DirectConnection);pump()
    assert not [m for m in messages if any(t in m for t in ('ReferenceError','TypeError','Binding loop','is not defined'))],messages
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print(json.dumps(dict(cases=cases,errors=0,mode='invoice/wizard light/dark, normal/compact')))

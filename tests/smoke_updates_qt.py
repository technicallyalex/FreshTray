"""Isolated update UI tests; never requests a public release or installs an app."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtCore import QUrl,QObject,QMetaObject,QCoreApplication,QEvent,QPointF
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault,Preferences
from freshtray.updates import Release
root=Path(__file__).resolve().parents[1]
app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
for font in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
def pump(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def wait(test):
    end=time.monotonic()+5
    while not test() and time.monotonic()<end:pump(.02)
    assert test()
def click(w,name):
    assert QMetaObject.invokeMethod(w.findChild(QObject,name),'clicked');pump()
with tempfile.TemporaryDirectory(prefix='FreshTray-Update-UI-') as d,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(d);prefs=Preferences(folder/'settings.json');prefs.save(reminders=False)
    b=Controller(Demo(),Vault(folder/'vault.dpapi'),prefs,root/'src/assets',root/'src/main.pyw',True,tray=False)
    b.screen_geometry=lambda:dict(x=0,y=0,width=960,height=520)
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b)
    e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects();w=e.rootObjects()[0];b.window=w;w.show();b.start();wait(lambda:not b.state['busy']);pump(.3)
    manager=b.updater;assert not manager.start_timer.isActive(),'Demo must never check automatically'
    b.selectPanel('settings');b.connectionSection(False);pump(.5)
    assert w.findChild(QObject,'checkUpdates')
    fake=Release('0.3','## Improvements\n\n'+'Long release notes.\n'*60,'https://github.com/technicallyalex/FreshTray/releases/tag/v0.3','','',2048,'')
    dialog=w.findChild(QObject,'updateDialog')
    with patch('freshtray.updates.latest_release',return_value=fake) as check:
        click(w,'checkUpdates');wait(lambda:manager.state['phase']=='available')
        assert dialog.property('visible') and check.call_count==1
        assert w.findChild(QObject,'updateNotes').property('text')==fake.notes
        assert not w.findChild(QObject,'downloadUpdate').property('enabled'),'Source mode must not replace Python'
        click(w,'dismissUpdate');assert not dialog.property('visible')
        assert Preferences(folder/'settings.json').data['dismissed_update']=='0.3'
        manager.check(False);wait(lambda:manager.state['phase']=='available');assert not dialog.property('visible')
        manager.checkUpdates();wait(lambda:manager.state['phase']=='available');assert dialog.property('visible')
    manager.setAutoCheck(False);assert not Preferences(folder/'settings.json').data['auto_updates']
    manager.portable=True;manager.changed.emit()
    def download(release,cache,cancel,progress):
        progress(50);time.sleep(.1);return dict(stage=str(folder/'stage'),download=str(folder/'new.exe'),digest='0'*64,version='0.3')
    with patch('freshtray.updates.download',side_effect=download):
        click(w,'downloadUpdate');wait(lambda:manager.state['phase']=='ready')
    b.setField('log','note','Unsaved work')
    with patch('freshtray.updates.prepare_install') as prepare:
        click(w,'installUpdate');assert 'draft' in manager.state['message'];prepare.assert_not_called()
    b.forms['log']=dict(b.baselines['log']);b.syncing=True
    click(w,'installUpdate');assert manager.state['phase']=='ready';b.syncing=False
    stopped=[]
    b.shutdown=lambda:stopped.append(True)
    with patch('freshtray.updates.prepare_install',return_value=str(folder/'plan.json')),patch('freshtray.updates.spawn') as spawn:
        click(w,'installUpdate');wait(lambda:bool(stopped));assert spawn.call_count==1
        assert spawn.call_args.args[0][1]=='--apply-update'
    assert b._installing
    for theme in ('light','dark'):
        b.update_preparation_failed();b.applySetting('theme',theme);manager.put(phase='available',visible=True);pump(.3)
        w.grabWindow().save(str(root/'.build'/f'update-dialog-{theme}.png'))
        for name in ('updateNotesScroll','downloadUpdate','dismissUpdate'):
            item=w.findChild(QObject,name);pos=item.mapToScene(QPointF(0,0))
            assert pos.x()>=0 and pos.y()>=0 and pos.x()+item.width()<=w.width()+1 and pos.y()+item.height()<=w.height()+1,(name,pos)
    manager.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close()
    b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS: update notes, dismissal persistence, manual checks, source safety, background download, draft/sync guards and install handoff; no network or real install.')

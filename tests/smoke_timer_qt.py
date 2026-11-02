"""Timer lifecycle and QML rendering with synthetic data; never writes to FreshBooks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl,QObject,qInstallMessageHandler,QCoreApplication,QEvent,QPoint
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtGui import QFontDatabase
from freshtray.qt_app import Controller
from freshtray.work_timer import WorkTimer
from freshtray.demo import Demo
from freshtray.storage import Preferences,Vault

app=QApplication([]);QQuickStyle.setStyle('Basic');project=Path(__file__).resolve().parents[1]
for font in (project/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
messages=[];qInstallMessageHandler(lambda kind,ctx,msg:messages.append(msg))
def pump(seconds=.2):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def settle(b):
    end=time.monotonic()+8
    while b.state['busy'] and time.monotonic()<end:pump(.02)
    assert not b.state['busy'];pump()
with tempfile.TemporaryDirectory() as d,patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(d);prefs=Preferences(folder/'settings.json');prefs.save(reminders=False)
    provider=Demo();b=Controller(provider,Vault(folder/'vault.dpapi'),prefs,project/'src/assets',project/'src/main.pyw',True,tray=False)
    errors=[];b.error.connect(errors.append)
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b);e.load(QUrl.fromLocalFile(str(project/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),messages
    w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b);b.selectPanel('timer');pump(.4)
    t=b.work_timer;t.setting('popout',True);pump();assert t.state['popout']
    pop=w.findChild(QObject,'timerPopout');assert pop and pop.isVisible()
    t.primary();assert t.status=='running';pump(.1);assert t.elapsed()>0
    main_clock=w.findChild(QObject,'timerMainClock');assert main_clock.property('animating') is True
    t.pause();held=t.elapsed();pump(.1);assert t.elapsed()==held
    assert main_clock.property('animating') is False
    frozen=main_clock.property('seconds');pump(.15);assert main_clock.property('seconds')==frozen
    t.pause();pump(.05);assert t.elapsed()>held;t.pause()
    t.seconds=90;t.persist()
    restored=WorkTimer(b);assert restored.status=='paused' and abs(restored.elapsed()-90)<.01
    restored.ui.stop();restored.checkpoint.stop();restored.deleteLater()
    t.primary();assert t.status=='review';t.duration('00:01:31');assert t.elapsed()==91
    before=len(provider.entries);t.primary();settle(b);assert t.status=='idle' and len(provider.entries)==before+1
    last=provider.entries[max(provider.entries)];assert last['duration']==91 and last['is_logged'] is True
    assert 'T' in last['started_at']
    for kind in ('digital','flip','analog','station'):
        t.setting('face',kind);pump(.2)
        assert w.findChild(QObject,'timerMainClock').property('kind')==kind
        t.setting('condensed',True);pump();assert pop.width()<=224
        t.setting('condensed',False);pump()
        (project/'.build').mkdir(exist_ok=True);w.grabWindow().save(str(project/'.build'/('timer-'+kind+'.png')))
        pop.grabWindow().save(str(project/'.build'/('timer-popout-'+kind+'.png')))
        for x,y in [(-500,-500),(9999,9999)]:
            pop.setX(x);pop.setY(y);pump(.05)
            area=app.primaryScreen().availableGeometry()
            assert area.contains(pop.geometry()),(kind,pop.geometry(),area)
        assert main_clock.property('durationText')=='00:00:00'
        still=pop.grabWindow();pump(.15);assert pop.grabWindow()==still
    t.setting('opacity',.65);assert t.state['opacity']==.65
    t.setting('face','analog');t.setting('condensed',True);pump()
    area=app.primaryScreen().availableGeometry();pop.setX(area.x()+100);pop.setY(area.y()+1);pump()
    QTest.mouseMove(pop,QPoint(80,80));pump(.4)
    hint=w.findChild(QObject,'timerMoveHint');assert hint and hint.isVisible(),(hint.property('opacity'),hint.property('visible'),hint.geometry(),pop.geometry(),pop.property('showHint'),pop.property('hintHasSpace'),pop.findChild(QObject,'timerCondensedMouse').property('containsMouse'),pop.findChild(QObject,'timerCondensedMouse').property('enabled'),pop.findChild(QObject,'timerCondensedMouse').property('width'),pop.findChild(QObject,'timerCondensedMouse').property('height'))
    assert hint.y()>=pop.y()+pop.height(),(hint.geometry(),pop.geometry())
    pop.setY(area.bottom()-pop.height()+1);pump(.2)
    assert hint.y()+hint.height()<=pop.y(),(hint.geometry(),pop.geometry())
    QTest.mouseMove(pop,QPoint(-20,-20));pump(.3)
    assert hint.property('opacity')==0
    assert not errors,errors
    assert not [m for m in messages if any(s in m for s in ('ReferenceError','TypeError','binding loop','failed to load','Cannot assign'))],messages
    b.shutdown();w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS timer: pause/resume, encrypted restore, exact duration, save once, four faces, independent idle popout, compact mode, opacity and QML rendering.')

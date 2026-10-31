"""Expanded release QA: isolated fictional data; no provider/network access.

Run in separate processes with --scale to exercise Qt's actual pixel ratios.
Detailed results and selected screenshots stay under .build/qa/.
"""
import argparse
import os
parser=argparse.ArgumentParser()
parser.add_argument('--scale',default='1')
args=parser.parse_args()
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['QT_SCALE_FACTOR']=args.scale
import sys, json, time, tempfile
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Property,QUrl,QPointF,QObject,QCoreApplication,QEvent,qInstallMessageHandler
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle
from unittest.mock import patch
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault,Preferences
from freshtray.model import entry_payload

root=Path(__file__).resolve().parents[1]
out=root/'.build/qa'/('scale-'+args.scale);out.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
for font in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
messages=[]
qInstallMessageHandler(lambda kind,ctx,text:messages.append(text))
patch('freshtray.alert_sound.winsound.PlaySound').start()
class AuditController(Controller):
    @Property(bool,constant=True)
    def reducedMotion(self):return True
class SyncState:
    data={'outbox':[],'catalogs':{}}
    def status(self):
        return dict(online=False,count=2,message='Offline. Saved changes will sync when the connection returns.',
                    problems=[dict(id='qa',action='update',day='2026-08-03',note='Fictional review example',status='conflict',message='This entry changed in FreshBooks. Review the saved version before applying another change.')])
    def legacy_pending(self):return False

def pump(seconds=.07):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def settle(b,w):
    end=time.monotonic()+5
    while time.monotonic()<end:
        pump(.02)
        timer=w.findChild(QObject,'settingsRefitTimer')
        if not b.state['busy'] and not w.property('animating') and not timer.property('running'):
            pump(.05)
            if not timer.property('running'):return
    raise AssertionError('Layout never settled')
def xy(item):return item.mapToScene(QPointF(0,0))
def bounds(item,w):
    p=xy(item);issues=[]
    if item.width()<=0 or item.height()<=0:issues.append('zero size')
    if p.x() < -1 or p.y() < -1 or p.x()+item.width()>w.width()+1 or p.y()+item.height()>w.height()+1:issues.append('outside window')
    parent=item.parentItem()
    while parent:
        if parent.clip():
            q=item.mapToItem(parent,QPointF(0,0))
            if q.x() < -1 or q.y() < -1 or q.x()+item.width()>parent.width()+1 or q.y()+item.height()>parent.height()+1:
                issues.append('clipped by '+(parent.objectName() or parent.metaObject().className()));break
        parent=parent.parentItem()
    return issues
names={
 'log':['businessChoice','logClient','logDate','logHours','logSave'],
 'month-five':['monthlyCalendar','monthClient','monthDate','monthHours','monthSave','dayEntriesArea'],
 'month-six':['monthlyCalendar','monthClient','monthDate','monthHours','monthSave','dayEntriesArea'],
 'preferences':['dropdownSorting','versionLink','remindMeDelay','popupSoundChoice','remindMeSoundChoice','popupVolume'],
 'connection':['oauthClient','oauthSecret','oauthRedirect','oauthSignIn','refreshAccountData','disconnectAccount'],
 'return':['oauthReturned','oauthFinish','oauthBack','refreshAccountData','disconnectAccount'],
 'review':['syncReviewChoice','discardSyncChange','refreshAccountData','disconnectAccount'],
 'review-setup':['oauthClient','oauthSecret','oauthRedirect','oauthSignIn','backToSyncReview','disconnectAccount']}
results=[]
with tempfile.TemporaryDirectory(prefix='FreshTray-QA-') as temp:
    folder=Path(temp);prefs=Preferences(folder/'settings.json');prefs.save(reminders=False,popup_sound=False)
    provider=Demo()
    # Six-week month, including enough entries to require pagination.
    for day in (3,4,5,6,7,10,11,12,13,14,17,18,19,20,21,24,25,26,27,28,31,3,3):
        provider.submit(1,entry_payload(1,date(2026,8,day).isoformat(),'8:00','Fictional QA entry',True,42))
    b=AuditController(provider,Vault(folder/'vault.dpapi'),prefs,root/'src/assets',root/'src/main.pyw',True,tray=False)
    b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop()
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b)
    e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),messages
    w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b,w)
    settings=w.findChild(QObject,'settingsPanel')
    for width,height in ((1280,720),(960,520)):
      b.screen_geometry=lambda width=width,height=height:dict(x=0,y=0,width=width,height=height)
      for theme in ('light','dark'):
        b.applySetting('theme',theme)
        for state in names:
            b.offline=None;b._s['demo']=True;b._s['authStarted']=False;settings.setProperty('showConnectionSetup',False)
            b.forms['log']=dict(b.baselines['log']);b.forms['month']=dict(b.baselines['month']);b.originals['month']=None
            b.emit()
            if state=='log':b.selectPanel('log')
            elif state.startswith('month'):
                b.selectPanel('month');settle(b,w)
                b.chooseMonth(2026,8 if state=='month-six' else 10);settle(b,w)
                b.selectDay('2026-08-03' if state=='month-six' else '2026-10-01')
            else:
                b.connectionSection(state!='preferences');b.selectPanel('settings')
                if state=='return':b._s['authStarted']=True;b.emit()
                if state.startswith('review'):
                    b._s['demo']=False;b.offline=SyncState();b.emit()
                    settings.setProperty('showConnectionSetup',state=='review-setup')
            settle(b,w)
            issues=[]
            strip=w.findChild(QQuickItem,'mainTabStrip');frame=w.findChild(QQuickItem,'folderPanel')
            seam=xy(frame).y()-(xy(strip).y()+strip.height())
            if abs(seam)>1:issues.append('folder/tab seam offset '+str(seam))
            if xy(frame).y()+frame.height()>w.height()+1:issues.append('folder frame extends below window')
            if w.findChild(QQuickItem,'appTitleBar').height()!=43 or strip.height()!=46:issues.append('header dimensions changed')
            for name in names[state]:
                item=w.findChild(QQuickItem,name)
                if item is None:issues.append(name+': missing QA handle');continue
                if not item.isVisible():issues.append(name+': unexpectedly hidden');continue
                issues.extend(name+': '+issue for issue in bounds(item,w))
            if state.startswith('month'):
                cal=w.findChild(QQuickItem,'monthlyCalendar')
                def descendants(item):
                    for child in item.childItems():
                        yield child
                        yield from descendants(child)
                cells=[c for c in descendants(cal) if c.objectName()=='calendarDay']
                if len(cells) not in (35,42):issues.append('calendar day delegates missing')
                if cells and min(c.height() for c in cells)<26:issues.append('calendar cells below 26 logical pixels')
            if state=='month-six':
                size=1 if w.height()<600 else 2
                if b.state.get('entryPageSize',2)!=size:issues.append('incorrect compact pagination capacity')
                b.entryPage(99)
                if b.state['entryPage']!=(len(b.state['entries'])-1)//size:issues.append('pagination cannot reach last entry')
                b.entryPage(0)
                previous=w.findChild(QQuickItem,'dayEntriesArea').height()
                b.selectDay('2026-08-02');pump(.05)
                if w.findChild(QQuickItem,'dayEntriesArea').height()!=previous:issues.append('empty day changes calendar allocation')
                b.selectDay('2026-08-03');pump(.05)
            if state=='review-setup':
                if w.findChild(QQuickItem,'syncReviewChoice').isVisible():issues.append('recovery details overlap connection setup')
            results.append(dict(scale=args.scale,area=[width,height],theme=theme,state=state,window=[w.width(),w.height()],dpr=w.devicePixelRatio(),issues=issues))
            if issues or (theme=='light' and state in ('connection','preferences','month-six','review-setup')):
                w.grabWindow().save(str(out/f'{width}-{height}-{theme}-{state}.png'))
    b.offline=None
    b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop()
    b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);pump(.02)
errors=[m for m in messages if any(x in m for x in ('ReferenceError','TypeError','Binding loop','Unable to assign','failed to load'))]
report=dict(cases=results,runtime_errors=errors)
(out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
failed=[c for c in results if c['issues']]
print(json.dumps(dict(scale=args.scale,cases=len(results),failed=len(failed),errors=len(errors),sample=failed[:4])))
raise SystemExit(bool(failed or errors))

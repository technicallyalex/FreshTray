"""Offline Qt Quick lifecycle, editing, cache and layout checks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl, QObject, qInstallMessageHandler, QCoreApplication, QEvent, QPointF, QMetaObject, Qt, Q_ARG, QDateTime
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuick import QQuickItem
from PySide6.QtGui import QFontDatabase
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault, Preferences
from freshtray.api import ApiError
from freshtray import __version__
from datetime import date

project=Path(__file__).resolve().parents[1]
sound_mock=patch('freshtray.alert_sound.winsound.PlaySound').start()
app=QApplication([])
QQuickStyle.setStyle('Basic')
for font in (project/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
messages=[]
def message(kind, context, text):
    messages.append(text)
    print(text,flush=True)
qInstallMessageHandler(message)

def pump(seconds=.25):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.processEvents();time.sleep(.005)

def settle(b):
    until=time.monotonic()+8
    while b.state['busy'] and time.monotonic()<until:
        pump(.03)
    assert not b.state['busy']
    pump(.3)

class CountingDemo(Demo):
    def __init__(self):
        super().__init__();self.reads=0;self.fail=False
    def entries_for_month(self,*args):
        self.reads+=1;time.sleep(.23)
        if self.fail:raise ApiError('Offline test failure')
        return super().entries_for_month(*args)

with tempfile.TemporaryDirectory() as d:
    folder=Path(d)
    prefs=Preferences(folder/'settings.json');prefs.save(reminders=False)
    provider=CountingDemo()
    b=Controller(provider,Vault(folder/'vault.dpapi'),prefs,project/'src/assets',project/'src/main.pyw',True,tray=False)
    errors=[];b.error.connect(errors.append)
    e=QQmlApplicationEngine()
    e.rootContext().setContextProperty('backend',b)
    print('Loading QML',flush=True)
    e.load(QUrl.fromLocalFile(str(project/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),'QML root failed to load'
    w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b)
    assert b.state['catalogReady'],errors
    assert w.findChild(QObject,'versionLink').property('text')=='FreshTray '+__version__
    assert w.findChild(QObject,'businessCard') is not None
    assert w.findChild(QObject,'saveSettings') is None
    settings_panel=w.findChild(QObject,'settingsPanel')
    assert w.findChild(QObject,'settingsSectionOutline').property('height')>100
    assert w.findChild(QObject,'settingsSectionOutline').property('fading') is True
    assert w.findChild(QObject,'folderOutline').property('fading') is True
    assert w.findChild(QObject,'preferencesSectionTab') is not None
    assert w.findChild(QObject,'connectionSectionTab') is not None
    assert QMetaObject.invokeMethod(settings_panel,'change',Qt.DirectConnection, Q_ARG('QVariant','theme'), Q_ARG('QVariant','dark'))
    assert prefs.data['theme']=='dark'
    b.applySetting('theme','light')
    w.grabWindow().save(str(project/'.build/qt-log.png'))
    b.selectPanel('month');settle(b)
    assert b.state['monthReady'],errors
    assert w.findChild(QObject,'calendarFrame').property('fading') is False
    assert b.state['years']==sorted(b.state['years'],reverse=True)
    w.grabWindow().save(str(project/'.build/qt-month.png'))
    print('Loaded Qt forms',w.width(),w.height(),flush=True)
    # Switching panels and editing text must not fetch month data again.
    reads=provider.reads
    for _ in range(8):b.selectPanel('log');b.selectPanel('settings');b.selectPanel('month')
    b.setField('month','note','Draft survives panel changes')
    pump(.3)
    assert provider.reads==reads
    assert b.forms['month']['note']=='Draft survives panel changes'
    b.clearForm('month');b.answer(True)
    # Add directly in the monthly editor, then edit the same ID.
    empty_calendar_height=w.findChild(QQuickItem,'monthlyCalendar').height()
    b.setField('month','hours','1:15');b.setField('month','note','Qt integration test')
    old_ids=set(provider.entries)
    b.submit('month');settle(b)
    new_ids=set(provider.entries)-old_ids
    assert len(new_ids)==1
    assert abs(w.findChild(QQuickItem,'monthlyCalendar').height()-empty_calendar_height)<=1, 'Empty and populated days must not resize the calendar'
    entry_id=new_ids.pop()
    b.editEntry(str(entry_id));settle(b)
    assert b.originals['month']['id']==entry_id
    b.setField('month','hours','2:30');b.submit('month');settle(b)
    assert provider.entries[entry_id]['duration']==9000
    assert len(set(provider.entries)-old_ids)==1
    # Billed edits retain billing state and work without creating duplicates.
    provider.entries[entry_id]['billed']=True
    b.editEntry(str(entry_id));settle(b)
    assert b.state['monthForm']['billed']
    b.setField('month','note','Billed note edit');b.submit('month');settle(b)
    assert provider.entries[entry_id]['billed'] is True
    # A fresh read detects external changes before overwriting an entry.
    b.editEntry(str(entry_id));settle(b)
    provider.entries[entry_id]['note']='Changed elsewhere'
    b.setField('month','note','Local unsaved note');b.submit('month');settle(b)
    assert errors and 'changed elsewhere' in errors.pop()
    assert b.forms['month']['note']=='Local unsaved note'
    b.clearForm('month');b.answer(True)
    preserved=dict(b.forms['month']);kept_ids=[entry['id'] for entry in b.entries]
    b.deleted_entry({'deleted':True,'id':entry_id,'business_id':999})
    assert b.forms['month']==preserved and [entry['id'] for entry in b.entries]==kept_ids
    # Multiple saved entries get multiple markers. Delete requires confirmation,
    # cancellation is harmless, and an unrelated draft survives successful deletion.
    count_before=next(cell['entryCount'] for cell in b.calendar if cell['iso']==b.selected.isoformat())
    assert count_before>=1
    b.setField('month','hours','0:30');b.setField('month','note','Delete smoke fixture')
    previous=set(provider.entries);b.submit('month');settle(b)
    deletion_id=(set(provider.entries)-previous).pop()
    assert next(cell['entryCount'] for cell in b.calendar if cell['iso']==b.selected.isoformat())==count_before+1
    b.deleteEntry(str(deletion_id));b.answer(False);settle(b)
    assert provider.entries[deletion_id]['active']
    b.setField('month','note','Unrelated draft to preserve')
    b.deleteEntry(str(deletion_id));b.answer(True);settle(b)
    assert provider.entries[deletion_id]['active'] is False
    assert b.forms['month']['note']=='Unrelated draft to preserve'
    assert next(cell['entryCount'] for cell in b.calendar if cell['iso']==b.selected.isoformat())==count_before
    b.clearForm('month');b.answer(True)
    assert w.findChild(QObject,'calendarMonthTotal').property('text')==b.state['monthTotal']
    # Uncached reads show a delayed skeleton; failures leave writes disabled.
    provider.fail=True;b.api.clear('month');b.month_valid=False
    b.load_month();pump(.17)
    assert b.state['busy']
    assert any(item.property('shown') for item in w.findChildren(QObject,'loadingSkeleton'))
    settle(b)
    assert errors.pop()=='Offline test failure'
    assert not b.state['monthReady']
    provider.fail=False;b.load_month();settle(b)
    assert b.state['monthReady']
    for dialog in ('errorDialog','confirmDialog'):
        QMetaObject.invokeMethod(w.findChild(QObject,dialog),'close')
    # Cover 100%, 150% and 200% logical work areas, plus compact laptop space.
    for width,height in [(1920,1040),(1280,680),(960,520)]:
        b.screen_geometry=lambda width=width,height=height:dict(x=0,y=0,width=width,height=height)
        for theme in ('light','dark'):
            values=dict(b.state['settings'],theme=theme)
            b.saveSettings(values)
            for panel in ('log','month','settings'):
                b.selectPanel(panel);settle(b)
                if panel=='settings':b.connectionSection(False);pump(.3)
                assert w.width()<=width and w.height()<=height,(width,height,panel,w.width(),w.height())
                names={'log':['logClient','logDate','logHours','logNote','logSave'],
                       'month':['monthlyCalendar','monthClient','monthDate','monthHours','monthNote','monthSave'],
                       'settings':['dropdownSorting','versionLink','remindMeDelay','popupSoundToggle']}[panel]
                for name in names:
                    item=w.findChild(QQuickItem,name);assert item is not None,name
                    point=item.mapToScene(QPointF(0,0))
                    assert point.x()>=0 and point.y()>=0,(name,point)
                    assert point.x()+item.width()<=w.width()+1,(width,height,panel,name,'horizontal overflow')
                    assert point.y()+item.height()<=w.height()+1,(width,height,panel,name,point,item.height(),w.height())
                if panel=='month':
                    assert w.findChild(QQuickItem,'calendarTotalsFooter').height()==36
                    stack=[w.findChild(QQuickItem,'monthlyCalendar')];cells=[]
                    while stack:
                        item=stack.pop();stack.extend(item.childItems())
                        if item.objectName()=='calendarDay':cells.append(item)
                    assert cells and min(item.height() for item in cells)>=24,('Calendar rows collapsed',[item.height() for item in cells])
                if panel in ('log','month'):
                    scope='log' if panel=='log' else 'month'
                    card=w.findChild(QQuickItem,'logEditorCard' if panel=='log' else 'monthlyEditorCard')
                    button=w.findChild(QQuickItem,scope+'Save')
                    point=button.mapToItem(card,QPointF())
                    assert abs(card.width()-point.x()-button.width()-card.property('rightPadding'))<=1,(panel,'right padding')
                    assert abs(card.height()-point.y()-button.height()-card.property('bottomPadding'))<=1,(panel,'bottom padding',point,card.height())
                w.grabWindow().save(str(project/f'.build/qt-{panel}-{width}-{theme}.png'))
                if panel=='settings':
                    settings=w.findChild(QQuickItem,'settingsPanel')
                    version=w.findChild(QQuickItem,'versionLink')
                    assert version.mapToItem(settings,QPointF()).y()+version.height()<=settings.height()+1,'Settings footer clipped'
                    b.connectionSection(True);pump(.3)
                    for name in ('oauthClient','oauthSecret','oauthRedirect'):
                        item=w.findChild(QQuickItem,name);point=item.mapToScene(QPointF())
                        assert point.y()+item.height()<=w.height()+1,(width,height,name)
    # Docked fitting anchors the logical window to the working area's bottom right.
    b.selectPanel('log')
    b.saveSettings(dict(b.state['settings'],docked_mode=True));pump(.4)
    assert abs(w.x()+w.width()-952)<=2 and abs(w.y()+w.height()-512)<=2
    b.saveSettings(dict(b.state['settings'],docked_mode=False));pump(.3)
    # Date picker and independent reminder window work without the main window.
    b.selectPanel('log');pump(.3)
    picker=w.findChild(QObject,'logPicker');assert picker is not None
    assert QMetaObject.invokeMethod(picker,'open');pump(.1)
    assert picker.property('visible')
    QMetaObject.invokeMethod(picker,'close')
    # Sound selection/volume persist, preview uses that preset, and mute is silent.
    b.applySetting('popup_sound_choice','warm_bell'); b.applySetting('popup_volume',35)
    assert Preferences(folder/'settings.json').data['popup_sound_choice']=='warm_bell'
    assert Preferences(folder/'settings.json').data['popup_volume']==35
    before_preview=sum(call.args[0] is not None for call in sound_mock.call_args_list)
    b.previewSound(); pump(.2)
    assert sum(call.args[0] is not None for call in sound_mock.call_args_list)==before_preview+1
    assert 'warm_bell-35.wav' in str(sound_mock.call_args.args[0])
    b.applySetting('popup_volume',0); b.previewSound(); pump(.1)
    assert sum(call.args[0] is not None for call in sound_mock.call_args_list)==before_preview+1
    b.applySetting('popup_sound_choice','ethereal'); b.applySetting('popup_volume',60)
    before_sound=sum(call.args[0] is not None for call in sound_mock.call_args_list)
    w.hide();b.testReminder();pump(.4)
    assert sum(call.args[0] is not None for call in sound_mock.call_args_list)==before_sound+1
    reminder=w.findChild(QObject,'reminderWindow');assert reminder.isVisible()
    assert abs(reminder.x()+(reminder.width()/2)-480)<=1
    assert abs(reminder.y()+(reminder.height()/2)-260)<=1
    assert w.findChild(QObject,'reminderDragHandle') is not None
    clock=w.findChild(QObject,'reminderPunchClock');assert clock is not None
    shown=clock.property('displayedTime')
    assert abs(shown.msecsTo(QDateTime.currentDateTime()))<2000,'Reminder must capture local PC time on spawn'
    hands=(clock.property('hourAngle'),clock.property('minuteAngle'),clock.property('secondAngle'))
    assert hands==((shown.time().hour()%12)*30+shown.time().minute()*.5,shown.time().minute()*6,shown.time().second()*6)
    reminder.grabWindow().save(str(project/'.build/qt-reminder-rest.png'))
    if not b.reducedMotion:
        pump(1.8);assert clock.property('feed')>0
    assert hands==(clock.property('hourAngle'),clock.property('minuteAngle'),clock.property('secondAngle')),'Clock hands must stay still while the card moves'
    reminder.grabWindow().save(str(project/'.build/qt-reminder-punch.png'))
    before_sound=sum(call.args[0] is not None for call in sound_mock.call_args_list)
    reminder.setX(30);reminder.setY(40);b.testReminder();pump(.05)
    assert sum(call.args[0] is not None for call in sound_mock.call_args_list)==before_sound
    assert reminder.x()==30 and reminder.y()==40,'Visible reminder must not jump while being used'
    pump(.35)
    assert Preferences(folder/'settings.json').data['reminder_position']=={'x':30,'y':40}
    reminder.hide();pump(.05);assert clock.property('feed')==0
    b.prefs=Preferences(folder/'settings.json')
    b.delayed_reminder.prefs=b.prefs
    b.testReminder();pump(.4)
    assert reminder.x()==30 and reminder.y()==40,'New presentation should restore saved position'
    assert reminder.opacity()==1 and not reminder.property('entering')
    reminder.hide();b.rememberReminderPosition(9000,-2000)
    b.testReminder();pump(.4)
    assert 0<=reminder.x() and reminder.x()+reminder.width()<=960
    assert 0<=reminder.y() and reminder.y()+reminder.height()<=520
    reminder.hide()
    b.applySetting('remind_me_minutes',1)
    b.applySetting('popup_sound_choice','warm_bell')
    b.applySetting('remind_me_sound_choice','punchcard')
    assert Preferences(folder/'settings.json').data['remind_me_sound_choice']=='punchcard'
    b.previewRemindMeSound(); pump(.2)
    assert str(sound_mock.call_args.args[0]).endswith('punchcard.wav')
    schedule=(prefs.data['time'],prefs.data['last_reminded'])
    b.testReminder();pump(.4)
    assert str(sound_mock.call_args.args[0]).endswith('warm_bell.wav')
    assert QMetaObject.invokeMethod(w.findChild(QObject,'reminderAgain'),'clicked')
    pump(.05);assert not reminder.isVisible()
    assert Preferences(folder/'settings.json').data['reminder_again_at']
    from datetime import datetime,timedelta,timezone
    now=datetime.now(timezone.utc)+timedelta(seconds=61)
    b.delayed_reminder.now=lambda:now
    assert b.deliver_delayed_reminder();pump(.4);assert reminder.isVisible()
    assert str(sound_mock.call_args.args[0]).endswith('punchcard.wav')
    assert not b.deliver_delayed_reminder()
    assert Preferences(folder/'settings.json').data['reminder_again_at'] is None
    assert (prefs.data['time'],prefs.data['last_reminded'])==schedule
    reminder.hide();b.applySetting('popup_sound',False)
    assert Preferences(folder/'settings.json').data['popup_sound'] is False
    before_sound=sum(call.args[0] is not None for call in sound_mock.call_args_list)
    b.testReminder();pump(.4)
    assert sum(call.args[0] is not None for call in sound_mock.call_args_list)==before_sound
    reminder.hide();b.logFromReminder();pump(.1);assert w.isVisible()
    assert not errors,errors
    b.executor.shutdown(wait=True)
    w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);pump(.05)
    assert not errors,errors
    assert not [m for m in messages if 'Error' in m or 'ReferenceError' in m or 'TypeError' in m],messages
print('PASS: Qt add/edit/conflict safety, cached navigation, skeleton/failure recovery, date picker, background reminder, and 18 panel/DPI/theme layouts.',flush=True)

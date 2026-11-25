"""Opt-in, isolated packaged wizard regression test. Never used with account data."""
import faulthandler
import json
import os
from PySide6.QtCore import QObject,QTimer,QMetaObject,Qt,qInstallMessageHandler,QPointF
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

def run_wizard_check(app,backend,engine,folder):
    folder.mkdir(parents=True,exist_ok=True)
    log=(folder/'wizard-diagnostic.log').open('w',encoding='utf-8')
    faulthandler.enable(log);faulthandler.dump_traceback_later(20,file=log,exit=True)
    def write(message):log.write(message+'\n');log.flush()
    def qt_message(kind,context,message):
        if log.tell()<150000:write('QT '+message)
    qInstallMessageHandler(qt_message)
    root=engine.rootObjects()[0];timer=QTimer(app);timer.setInterval(400);state={'step':-3}
    source='settings'
    def tick():
        try:
            step=state['step'];write('TICK '+str(step))
            wizard=root.findChild(QObject,'setupWizard')
            if 'expected' in state:
                if wizard.property('step')!=state.pop('expected'):raise RuntimeError('Wizard navigation did not complete')
            if step==-3:
                backend.selectPanel('invoices' if source=='invoices' else 'settings')
                if source!='invoices':backend.connectionSection(True)
            elif step==-2:root.grabWindow().save(str(folder/'before.png'))
            elif step==-1:
                button=next(x for x in root.findChildren(QQuickItem) if x.property('text')==('Setup wizard' if source=='invoices' else 'Connection setup wizard') and x.isVisible())
                point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
                write('MOUSE OPEN begin');QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point);write('MOUSE OPEN returned')
            elif 0<=step<4:
                if step==0 and not wizard.property('opened'):raise RuntimeError('Wizard did not open through its button')
                wizard.setProperty('step',step);write('STEP '+str(step));root.grabWindow().save(str(folder/('step-'+str(step)+'.png')))
                label='Next' if step==0 else 'Back'
                button=next(x for x in wizard.findChildren(QQuickItem) if x.property('text')==label and x.isVisible())
                point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
                QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point)
                state['expected']=1 if step==0 else step-1
            elif step==4:
                button=next(x for x in wizard.findChildren(QQuickItem) if x.property('text')=='Close' and x.isVisible())
                point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
                QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point)
                write('MOUSE CLOSE returned')
            elif 5<=step<20:
                if wizard.property('visible'):raise RuntimeError('Wizard does not respond to Close')
                refit=root.findChild(QObject,'settingsRefitTimer')
                if root.property('animating') or root.property('centerResize') or (refit and refit.property('running')):
                    raise RuntimeError('Connection panel remains stuck in resizing while idle')
                write('IDLE responsive; no resize/refit pending')
            else:
                write('PASS packaged wizard opened, rendered four steps, closed; event loop responsive')
                write('PASS packaged connection panel idle without rendered animation frames')
                timer.stop();faulthandler.cancel_dump_traceback_later();qInstallMessageHandler(None);backend.requestQuit();return
            state['step']+=1
        except Exception as exc:
            write('FAIL '+type(exc).__name__+': '+str(exc));timer.stop();faulthandler.cancel_dump_traceback_later();app.exit(2)
    timer.timeout.connect(tick);timer.start()
    app._wizard_diagnostic=(timer,log,qt_message)

"""Actual packaged panel-click/idle regression run with fictional local records."""
import faulthandler
import time
import json
from PySide6.QtCore import QTimer,QPointF,qInstallMessageHandler
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from .billing import blank_invoice

def run_panel_check(app,b,engine,folder,live_readonly=False):
    folder.mkdir(parents=True,exist_ok=True)
    log=(folder/'panel-cycle.log').open('w',encoding='utf-8');root=engine.rootObjects()[0]
    def write(value):log.write(str(value)+'\n');log.flush()
    failures=[]
    def message(kind,context,value):
        if any(x in value for x in ('ReferenceError','TypeError','Binding loop','recursive rearrange')):failures.append(value);write(value)
    qInstallMessageHandler(message)
    faulthandler.dump_traceback_later(20,file=log,exit=True)
    bill=b.invoices
    if not live_readonly:
        bill.seller(dict(name='QA Studio',email='qa@example.invalid',address='Example address',currency='USD'))
        if not bill.store.data()['clients']:bill.store.add('clients',dict(name='QA Client',email='client@example.invalid'))
    routes=['log','month','timer','invoices','invoice-edit','invoice-preview','invoice-import','clients','estimates','preferences','connection']
    top=['log','month','timer','invoices','clients','estimates','preferences']
    sequence=[route for a in top for c in top if a!=c for route in (a,c)]+routes*2
    state=dict(index=0,phase='start',since=time.monotonic(),watch=time.monotonic(),transitions=0,samples=0,tween_frames=0,rapid=0,boot=time.monotonic(),prefetch='start',refreshes=0,idle_refits=0)
    timer=QTimer(app);timer.setInterval(80)
    def items(item):
        yield item
        for child in item.childItems():yield from items(child)
    def click(name):
        item=next((x for x in items(root.contentItem()) if x.objectName()==name),None)
        if not item or not item.isVisible():raise RuntimeError('Missing visible control '+name)
        point=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
        QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point)
    def finish(error=None):
        timer.stop();faulthandler.cancel_dump_traceback_later();qInstallMessageHandler(None)
        if live_readonly:
            summary=b.remote_api.transport.summary();write('LIVE_API '+json.dumps(summary))
            if not error and (summary['blocked_writes'] or any(not summary['successful_gets'].get(k) for k in ('profile','invoices','time_entries'))):error=RuntimeError('Required live reads were not verified')
        write(('FAIL '+str(error)) if error else 'PASS '+json.dumps(dict(visits=len(sequence),idle_samples=state['samples'],tween_frames=state['tween_frames'],dpr=root.devicePixelRatio())))
        if error:app.exit(2)
        else:b.requestQuit()
    def tick():
        try:
            now=time.monotonic()
            if now-state['watch']>5:faulthandler.dump_traceback_later(20,file=log,exit=True);state['watch']=now
            if failures:raise RuntimeError(failures[0])
            if b.state['busy']:
                state['since']=now;return
            if live_readonly and state['prefetch']!='done':
                if now-state['boot']>90:raise RuntimeError('Live startup reads did not finish')
                if not b.state['catalogReady']:raise RuntimeError('Live catalog unavailable')
                if state['prefetch']=='start':
                    bill.download();state['prefetch']='waiting';write('LIVE initial invoice refresh');return
                if bill.busy:return
                if bill.problem:raise RuntimeError('Live invoice refresh: '+bill.problem)
                state['prefetch']='done'
            if live_readonly and bill.busy and state['index']<len(sequence) and sequence[state['index']] in ('invoice-edit','invoice-preview','invoice-import'):
                state['since']=now;return
            if 'fixture' not in state:
                clients=bill.state['clients'];invoice=blank_invoice(str(clients[0]['id']))
                invoice['lines'][0].update(name='QA service',description='A wrapped description for panel QA.',rate='100')
                invoice['sync']='local' if bill.local else 'queued'
                state['fixture']=bill.store.put(bill.namespace(),invoice)['id']
            if state['rapid']<15:
                rapid=['log','month','timer','invoices','clients','estimates','settings']
                key=rapid[state['rapid']%len(rapid)]
                click(key+'Tab');write('RAPID '+str(state['rapid'])+' '+key);state['rapid']+=1;return
            if state['index']>=len(sequence):finish();return
            route=sequence[state['index']]
            if state['phase']=='start':
                if state['index']%len(routes)==0:b.applySetting('theme','light' if (state['index']//len(routes))%2==0 else 'dark')
                key='invoices' if route.startswith('invoice') else 'settings' if route in ('preferences','connection') else route
                click(key+'Tab')
                if route in ('preferences','connection'):click('connectionSectionTab' if route=='connection' else 'preferencesSectionTab')
                if route=='invoices':bill.back()
                if route=='invoice-edit':
                    bill.openInvoice(state['fixture'])
                if route=='invoice-preview':bill.showPreview()
                if route=='invoice-import':
                    bill.editPreview();bill.openImport()
                if live_readonly and route=='connection':
                    bill.download();state['refreshes']+=1;write('LIVE background refresh while in connection Settings')
                if b.state['panel']!=key:raise RuntimeError('Tab click did not select '+key)
                state.update(phase='settle',since=now,idle_refits=0);write('VISIT '+str(state['index'])+' '+route)
            elif state['phase']=='settle':
                if b.resizeAnimating:state['tween_frames']+=1
                if now-state['since']>3:raise RuntimeError('Panel resize did not settle: '+route)
                if now-state['since']>.65 and not b.resizeAnimating and not b.settingsFitPending:
                    state.update(phase='idle',since=now,geometry=(root.x(),root.y(),root.width(),root.height()))
            else:
                state['samples']+=1
                changed=b.resizeAnimating or b.settingsFitPending or (root.x(),root.y(),root.width(),root.height())!=state['geometry']
                if changed:
                    if not live_readonly or state['idle_refits']>=3:raise RuntimeError('Idle panel did not remain stable: '+route)
                    state['idle_refits']+=1;state.update(phase='settle',since=now);write('LIVE data update; checking bounded refit '+route);return
                if now-state['since']>=2:
                    state['index']+=1;state['phase']='start'
        except Exception as exc:finish(exc)
    timer.timeout.connect(tick);timer.start()
    app._panel_diagnostic=(timer,log,message)

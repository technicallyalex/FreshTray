"""Durable local stopwatch; reviewed entries use the existing offline write journal."""
from copy import deepcopy
from datetime import datetime, timezone
import time
import math
import re
import uuid
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QPoint
from PySide6.QtGui import QGuiApplication
from .model import entry_payload


class WorkTimer(QObject):
    changed = Signal()

    def __init__(self, controller):
        super().__init__(controller)
        self.owner = controller
        saved = controller.vault.get('work_timer') or {}
        if not isinstance(saved,dict):saved={}
        self.status = saved.get('status', 'idle')
        if self.status not in ('idle', 'running', 'paused', 'review'):
            self.status = 'idle'
        def number(value,default=0.):
            try:
                value=float(value)
                return value if math.isfinite(value) and value>=0 else default
            except (ValueError,TypeError):return default
        self.seconds = number(saved.get('seconds',0))
        if self.status == 'running':
            self.seconds += max(0., time.time()-number(saved.get('anchor'),time.time()))
        self.anchor = time.monotonic()
        self.started = saved.get('started', '')
        self.business_id = saved.get('business', '')
        self.identity = saved.get('identity', '')
        self.submission = saved.get('submission') if isinstance(saved.get('submission'),dict) else None
        self.request_id = saved.get('request_id')
        self.duration_valid = True
        self.saving = False
        self.restored_form = saved.get('form')
        if isinstance(self.restored_form,dict):
            for key,value in self.restored_form.items():
                if key in controller.forms['timer'] and type(value) is type(controller.forms['timer'][key]):
                    controller.forms['timer'][key]=deepcopy(value)
        self.ui = QTimer(self); self.ui.timeout.connect(self.tick); self.ui.start(1000)
        self.checkpoint = QTimer(self); self.checkpoint.timeout.connect(self.persist); self.checkpoint.start(10000)
        self.draft_save=QTimer(self);self.draft_save.setSingleShot(True);self.draft_save.timeout.connect(self.persist)

    def schedule_persist(self):
        self.draft_save.start(300)

    def elapsed(self):
        return self.seconds + (max(0., time.monotonic()-self.anchor) if self.status == 'running' else 0)

    def tick(self):
        if self.status == 'running':self.changed.emit()

    @Slot(result=float)
    def elapsedSeconds(self):
        return self.elapsed()

    @Slot(int,int,int,int,result='QVariantMap')
    def constrainPosition(self,x,y,width,height):
        screens=QGuiApplication.screens()
        if not screens:return dict(x=x,y=y,top=y,bottom=y+height)
        # Choose by window area, never by mouse position. Clamp the entire window.
        def overlap(screen):
            a=screen.availableGeometry()
            return max(0,min(x+width,a.right()+1)-max(x,a.x()))*max(0,min(y+height,a.bottom()+1)-max(y,a.y()))
        screen=max(screens,key=overlap)
        if overlap(screen)==0:
            center=QPoint(x+width//2,y+height//2)
            screen=min(screens,key=lambda s:(s.availableGeometry().center()-center).manhattanLength())
        area=screen.availableGeometry()
        return dict(x=max(area.x(),min(x,area.x()+area.width()-width)),
                    y=max(area.y(),min(y,area.y()+area.height()-height)),
                    top=area.y(),bottom=area.y()+area.height())

    @Property('QVariantMap', notify=changed)
    def state(self):
        p = self.owner.prefs.data
        face=p.get('timer_face','digital')
        if face not in ('digital','flip','analog','station'):face='digital'
        try:opacity=float(p.get('timer_opacity',1.))
        except (TypeError,ValueError):opacity=1.
        if not math.isfinite(opacity):opacity=1.
        return dict(status=self.status, seconds=self.elapsed(), started=self.started, saving=self.saving,
                    durationValid=self.duration_valid,submitted=bool(self.submission),
                    face=face, opacity=max(.4,min(1.,opacity)),
                    pinned=p.get('timer_pinned',True), popout=p.get('timer_popout',False),
                    condensed=p.get('timer_condensed',False))

    @Slot()
    def persist(self):
        self.draft_save.stop()
        try:
            self.owner.vault.update(work_timer=dict(status=self.status, seconds=self.elapsed(), anchor=time.time(),
                started=self.started, business=self.business_id, identity=self.identity, submission=self.submission,request_id=self.request_id,
                form=deepcopy(self.owner.forms['timer'])))
            return True
        except OSError:
            self.owner.error.emit('The timer could not be saved on this PC. Keep the app open and try again.')
            return False

    def settle(self):
        self.seconds=self.elapsed(); self.anchor=time.monotonic()

    @Slot()
    def primary(self):
        if self.saving: return
        if self.status == 'idle':
            b=self.owner
            if not b.business or not b._s['catalogReady'] or not b.forms['timer']['client']:
                b.error.emit('Choose a FreshBooks business and client before starting.'); return
            self.business_id=b.business['id']; self.identity=b.profile['id']
            self.seconds=0; self.anchor=time.monotonic(); self.started=datetime.now(timezone.utc).isoformat()
            self.status='running'
            if not self.persist():
                self.status='idle';self.seconds=0;self.started='';self.business_id='';self.identity=''
                self.changed.emit();return
        elif self.status in ('running','paused'):
            self.settle(); self.status='review'; self.persist()
        else:
            self.save_entry()
        self.changed.emit()

    @Slot()
    def pause(self):
        if self.saving or self.status not in ('running','paused'): return
        self.settle(); self.status='paused' if self.status=='running' else 'running'
        self.persist(); self.changed.emit()

    @Slot(str)
    def duration(self, text):
        if self.status!='review' or self.saving or self.submission: return
        try:
            if not re.fullmatch(r'\d{1,3}:[0-5]\d:[0-5]\d',text.strip()):raise ValueError()
            parts=[int(v) for v in text.strip().split(':')]
            if len(parts)!=3 or not 0<=parts[1]<60 or not 0<=parts[2]<60: raise ValueError()
            seconds=parts[0]*3600+parts[1]*60+parts[2]
            if not 0<seconds<=86400: raise ValueError()
        except ValueError:
            self.duration_valid=False;self.changed.emit()
            self.owner.error.emit('Enter duration as HH:MM:SS, between one second and 24 hours.'); return
        self.duration_valid=True;self.seconds=seconds; self.persist(); self.changed.emit()

    @Slot(str, 'QVariant')
    def setting(self, key, value):
        allowed={'face':('digital','flip','analog','station'),'opacity':None,'pinned':None,'popout':None,'condensed':None}
        if key not in allowed: return
        if key=='face' and value not in allowed[key]: return
        if key=='opacity':
            try:value=float(value)
            except (TypeError,ValueError):return
            if not math.isfinite(value):return
            value=max(.4,min(1.,value))
        if key in ('pinned','popout','condensed'): value=bool(value)
        try:self.owner.prefs.save(**{'timer_'+key:value})
        except OSError:self.owner.error.emit('This timer preference could not be saved.'); return
        self.changed.emit()

    @Slot(int,int)
    def position(self,x,y):
        try:self.owner.prefs.save(timer_position={'x':x,'y':y})
        except OSError:pass

    @Property('QVariantMap', constant=True)
    def savedPosition(self):
        value=self.owner.prefs.data.get('timer_position')
        return value if isinstance(value,dict) and all(type(value.get(k)) is int for k in ('x','y')) else {}

    @Slot()
    def discard(self):
        if self.saving:return
        message=('This timer already has a save awaiting confirmation. Review FreshBooks and sync first. Discarding this timer does not cancel or delete any submitted entry. Discard the local timer?' if self.submission else 'Discard this timer and its tracked time?')
        self.owner.confirm(message,self.clear,'Discard timer')

    def clear(self):
        previous=(self.status,self.seconds,self.started,self.business_id,self.identity,self.submission,self.request_id,deepcopy(self.owner.forms['timer']))
        self.status='idle';self.seconds=0;self.started='';self.business_id='';self.identity='';self.submission=None
        self.request_id=None;self.duration_valid=True
        self.owner.reset_form('timer')
        if not self.persist():
            self.status,self.seconds,self.started,self.business_id,self.identity,self.submission,self.request_id,form=previous
            self.owner.forms['timer']=form
            self.changed.emit();self.owner.emit();return False
        self.changed.emit();self.owner.emit();return True

    def save_entry(self):
        b=self.owner
        if b._s['busy']:return
        if not self.duration_valid:
            b.error.emit('Correct the reviewed duration before logging.');return
        if self.submission:
            self.recover_submission()
            if self.status=='idle':return
            if self.submission:
                b.error.emit('This timer already has a save awaiting confirmation. Review sync in connection settings before trying again.');return
        if not b.business or str(b.business['id'])!=str(self.business_id) or str(b.profile.get('id'))!=str(self.identity):
            b.error.emit('Reconnect to the business and account where this timer was started.');return
        try:
            f=b.forms['timer']; seconds=round(self.elapsed())
            if not 0<seconds<=86400:raise ValueError('Timer duration must be between one second and 24 hours. Adjust it before logging.')
            started=datetime.fromisoformat(self.started).astimezone()
            payload=entry_payload(f['client'],started.date().isoformat(),'0.01',f['note'],f['billable'],self.identity,f['project'],f['service'])
            payload['time_entry'].update(duration=seconds,started_at=self.started.replace('+00:00','Z'))
        except (ValueError,TypeError) as exc:b.error.emit(str(exc));return
        self.submission=deepcopy(payload)
        self.request_id=str(uuid.uuid4())
        if not self.persist():self.submission=None;return
        self.saving=True; self.changed.emit()
        def saved(entry):
            self.saving=False
            # Persist the acknowledgement before exposing another Start button.
            request=self.request_id
            cleared=self.clear(); b.month_valid=False;b.month_loaded=None;b._s['monthReady']=False;b.next_sync=0
            if cleared and b.offline:
                try:b.offline.forget_timer_receipt(request)
                except OSError:pass
            if b.offline:b.request_sync()
            else:b.toast.emit('Timer logged')
            if b._s['panel']=='month':b.load_month(force=True)
        def work():return b.offline.submit_timer(self.business_id,payload,self.request_id) if b.offline else b.api.submit(self.business_id,payload)
        if not b.run('save',work,saved):self.saving=False;self.submission=None;self.persist();self.changed.emit()

    def recover_submission(self):
        if not self.submission:return
        b=self.owner
        if b.offline and self.request_id:
            state=b.offline.timer_submission_state(self.request_id)
            if state in ('queued','saved'):
                request=self.request_id
                if self.clear():
                    try:b.offline.forget_timer_receipt(request)
                    except OSError:pass
                return
            # The durable outbox and receipt both lack this request, so no
            # provider dispatch happened. Retain the reviewed time for retry.
            if not b.vault.get('pending'):
                self.submission=None;self.request_id=None;self.saving=False;self.persist();self.changed.emit()
            return
        success=b.vault.get('last_success') or {}
        queued=b.offline and any(str(op['business'])==str(self.business_id) and op.get('payload')==self.submission for op in b.offline.data['outbox'])
        if queued or (str(success.get('business_id'))==str(self.business_id) and success.get('payload')==self.submission):
            self.clear()

    def save_failed(self):
        if not self.saving:return
        self.saving=False
        if self.owner.offline and self.request_id:
            self.recover_submission()
            if self.status=='idle':return
        # Retain uncertain submission guard; existing recovery UI owns reconciliation.
        elif not self.owner.vault.get('pending'):
            self.submission=None
        self.persist();self.changed.emit()

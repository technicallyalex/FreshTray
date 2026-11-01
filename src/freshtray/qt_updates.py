"""Background update presentation; does not share the FreshBooks network worker."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import json,queue,sys,time
from PySide6.QtCore import QObject,Property,Signal,Slot,QTimer
from . import __version__
from . import updates

class UpdateManager(QObject):
    changed=Signal()
    prompt=Signal()
    installRequested=Signal()
    prepared=Signal(str)
    preparationFailed=Signal()
    def __init__(self,prefs,demo=False,parent=None):
        super().__init__(parent)
        self.prefs=prefs;self.demo=demo;self.release=None;self.downloaded=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='FreshTrayUpdate')
        self.results=queue.Queue();self.cancel=Event();self.closed=False
        self.dismissed=False
        self.portable=bool(getattr(sys,'frozen',False) and not demo)
        self._state=dict(phase='idle',version='',notes='',message='',progress=0,visible=False)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(100)
        self.start_timer=QTimer(self);self.start_timer.setSingleShot(True);self.start_timer.timeout.connect(self.automatic_check)
        if self.portable:
            pending=self.prefs.data.get('update_plan')
            if pending:
                try:
                    path,_=updates.read_plan(pending)
                    result=path.parent/'result.json'
                    if result.exists():
                        record=json.loads(result.read_text(encoding='utf-8'))
                        if not record.get('ok'):
                            self._state.update(phase='error',message=record['message'])
                        self.prefs.save(update_plan=None)
                except (OSError,ValueError,KeyError,TypeError):pass
    @Property('QVariantMap',notify=changed)
    def state(self):
        return dict(self._state,portable=self.portable,autoCheck=bool(self.prefs.data.get('auto_updates',True)))
    def put(self,**values):self._state.update(values);self.changed.emit()
    def start(self):
        if self.portable:updates.prune_staging(updates.staging_root(),self.prefs.data.get('update_plan'))
        if self._state['phase']=='error':
            self.put(visible=True);self.prompt.emit();return
        if self.portable and self.prefs.data.get('auto_updates',True):self.start_timer.start(20000)
    def automatic_check(self):
        try:last=float(self.prefs.data.get('updates_checked_at',0))
        except (TypeError,ValueError):last=0
        if self.prefs.data.get('auto_updates',True) and time.time()-last>=86400:self.check(False)
    @Slot(bool)
    def setAutoCheck(self,value):
        try:self.prefs.save(auto_updates=bool(value));self.changed.emit()
        except OSError:self.put(message='The update preference could not be saved.')
    def job(self,kind,work):
        future=self.pool.submit(work)
        future.add_done_callback(lambda f:self.results.put((kind,f)))
    @Slot()
    def checkUpdates(self):self.check(True)
    def check(self,manual=True):
        if self.closed or self._state['phase'] in ('checking','downloading','preparing'):return
        if self._state['phase']=='ready':
            self.put(visible=True);self.prompt.emit();return
        self.dismissed=False
        self.release=None
        self.put(phase='checking',message='Checking for updates…',visible=manual,progress=0,version='',notes='')
        if manual:self.prompt.emit()
        try:self.prefs.save(updates_checked_at=time.time())
        except OSError:pass
        self.job('check',lambda:updates.latest_release(__version__))
    @Slot()
    def downloadUpdate(self):
        if not self.release or self._state['phase'] not in ('available','error'):return
        self.cancel.clear();self.put(phase='downloading',message='Downloading and verifying…',progress=0)
        self.job('download',lambda:updates.download(self.release,updates.staging_root(),self.cancel,lambda p:self.results.put(('progress',p))))
    @Slot()
    def installUpdate(self):
        if self.downloaded and self._state['phase']=='ready':self.installRequested.emit()
    def prepare(self,target,args):
        self.put(phase='preparing',message='Preparing to restart…')
        self.job('prepare',lambda:updates.prepare_install(self.downloaded,target,args))
    def install_error(self,message):self.put(phase='ready',message=message,visible=True)
    @Slot()
    def dismiss(self):
        if self._state['phase']=='preparing':return
        self.cancel.set();self.dismissed=True
        if self.release:
            try:self.prefs.save(dismissed_update=self.release.version)
            except OSError:pass
        self.put(visible=False)
    @Slot()
    def poll(self):
        while True:
            try:kind,item=self.results.get_nowait()
            except queue.Empty:return
            if kind=='progress':
                self.put(progress=item);continue
            try:
                value=item.result()
                if kind=='check':
                    self.release=value
                    if value:
                        visible=not self.dismissed and (self._state['visible'] or self.prefs.data.get('dismissed_update')!=value.version)
                        self.put(phase='available',version=value.version,notes=value.notes,message='A new version is available.',visible=visible)
                        if visible:self.prompt.emit()
                    else:self.put(phase='current',message='No newer release is available.')
                elif kind=='download':
                    self.downloaded=value;self.put(phase='ready',message='Download verified. Save your drafts, then install and restart.',progress=100)
                elif kind=='prepare':self.prepared.emit(value)
            except updates.Canceled:self.put(phase='available',message='Download canceled.',progress=0)
            except Exception as exc:
                message=str(exc) if isinstance(exc,updates.UpdateError) else 'Could not complete the update. Check your connection and folder permissions, then try again.'
                self.put(phase='error',message=message)
                if kind=='prepare':
                    self.put(phase='ready');self.preparationFailed.emit()
    def close(self):
        self.closed=True;self.cancel.set();self.timer.stop();self.start_timer.stop()
        self.pool.shutdown(wait=False,cancel_futures=True)

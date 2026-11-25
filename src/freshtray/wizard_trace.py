"""Local-only first-layout hang capture; no values, credentials or request data."""
import faulthandler
from datetime import datetime,timezone
from PySide6.QtCore import QTimer,qInstallMessageHandler

class WizardTrace:
    def __init__(self,owner):
        path=owner.vault.path.parent/'diagnostics';path.mkdir(parents=True,exist_ok=True)
        self.log=(path/'wizard-hang.log').open('a',encoding='utf-8')
        self.timer=QTimer(owner);self.timer.setSingleShot(True);self.timer.timeout.connect(self.ready)
        self.previous=qInstallMessageHandler(self.message)
    def message(self,kind,context,message):
        if any(s in message.lower() for s in ('polish loop','binding loop','recursive rearrange')) and self.log.tell()<150000:
            self.log.write('Qt layout warning: '+message+'\n');self.log.flush()
        if self.previous:self.previous(kind,context,message)
    def arm(self):
        self.log.write(datetime.now(timezone.utc).isoformat()+' wizard opening\n');self.log.flush()
        faulthandler.dump_traceback_later(5,file=self.log,exit=False)
        self.timer.start(1200)
    def ready(self):
        faulthandler.cancel_dump_traceback_later()
        self.log.write('Wizard opening: event loop responsive\n');self.log.flush()

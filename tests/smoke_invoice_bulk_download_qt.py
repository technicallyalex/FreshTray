"""Real FreshBooks adapter against deterministic fake transport; no real requests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile
from pathlib import Path
from copy import deepcopy
from datetime import date,timedelta
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from freshtray.qt_app import Controller
from freshtray.storage import Vault,Preferences
from freshtray.api import FreshBooks,ApiError
from freshtray.billing import totals
from freshtray.invoice_api import normalized
from test_offline import Server
from test_core import pair,CREDS
app=QApplication([]);root=Path(__file__).resolve().parents[1]
class InvoiceServer(Server):
    def __init__(self):super().__init__();self.invoices={};self.invoice_calls=[];self.fail_invoice=False
    def image(self,path,token):
        from PySide6.QtGui import QImage,QColor
        from PySide6.QtCore import QByteArray,QBuffer,QIODevice
        assert path=='/uploads/images/synthetic-logo'
        image=QImage(120,80,QImage.Format_ARGB32);image.fill(QColor('#0075dd'))
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);assert image.save(buffer,'PNG');return bytes(data)
    def __call__(self,method,path,body=None,token=None):
        url=urlsplit(path)
        if '/systems/systems/' in path:return {'response':{'result':{'system':{'name':'Connected Studio','info_email':'billing@example.invalid','street':'123 Example Street','city':'Example City','currency_code':'USD'}}}}
        if '/items/items' in path:return {'response':{'result':{'items':[],'pages':1}}}
        if '/expenses/expenses' in path:return {'response':{'result':{'expenses':[],'pages':1}}}
        if '/invoices/invoices' in path:
            suffix=url.path.split('/invoices/invoices')[1].strip('/')
            if method=='GET':return {'response':{'result':{'invoice':deepcopy(self.invoices[int(suffix)])}}} if suffix else {'response':{'result':{'invoices':list(deepcopy(self.invoices).values()),'pages':1}}}
            self.invoice_calls.append((method,deepcopy(body)))
            rid=int(suffix) if suffix else len(self.invoices)+1
            raw=deepcopy(body['invoice']);raw.update(id=rid,invoiceid=rid,invoice_number=raw.get('invoice_number') or f'{rid:06}',version=str(len(self.invoice_calls)),paid={'amount':'0.00'},display_status='draft')
            raw['due_date']=(date.fromisoformat(raw['create_date'])+timedelta(days=raw['due_offset_days'])).isoformat()
            raw['presentation']={'image_logo_src':'/uploads/images/synthetic-logo'}
            self.invoices[rid]=raw
            if self.fail_invoice:raise ApiError('Synthetic lost response',uncertain=True)
            return {'response':{'result':{'invoice':deepcopy(raw)}}}
        return super().__call__(method,path,body,token)
def settle(b):
    until=time.monotonic()+8
    while b.state['busy'] or b.invoices.busy:
        app.processEvents();time.sleep(.004);assert time.monotonic()<until
    for _ in range(15):app.processEvents();time.sleep(.004)

import threading
class TrackingVault(Vault):
    def __init__(self,path):super().__init__(path);self.billing_writes=[]
    def update(self,**values):
        if 'billing_v1' in values:self.billing_writes.append(threading.get_ident())
        return super().update(**values)
with tempfile.TemporaryDirectory() as d:
    d=Path(d);v=TrackingVault(d/'vault.dpapi');v.update(credentials=CREDS,tokens=pair());p=Preferences(d/'settings.json');p.save(reminders=False,standalone=False)
    server=InvoiceServer()
    for rid in range(1,316):
        server.invoices[rid]=dict(invoiceid=rid,id=rid,customerid=123,create_date='2026-01-01',invoice_number=str(rid),currency_code='USD',display_status='draft',paid={'amount':'0.00'},lines=[dict(name='QA service',description='A fictional invoice detail',qty='1',unit_cost={'amount':'10.00','code':'USD'}) for _ in range(25)])
    b=Controller(FreshBooks(v,server),v,p,root/'src/assets',root/'src/main.pyw',False,tray=False);b.offline.probe=lambda:True;b.sync_timer.stop();b.start();settle(b)
    inv=b.invoices;inv.activate()
    dirty=normalized(server.invoices[1]);dirty['sync']='queued';dirty['note']='Retain local edits';inv.store.put(inv.namespace(),dirty)
    v.billing_writes.clear();main_thread=threading.get_ident();inv.download();settle(b)
    assert not inv.problem,inv.problem
    assert len(inv.store.rows(inv.namespace()))==315
    assert len(v.billing_writes)==1,v.billing_writes
    assert v.billing_writes[0]!=main_thread,'Bulk invoice storage must run off the GUI thread'
    first=next(x for x in inv.store.rows(inv.namespace()) if x['id']==dirty['id']);assert first['note']=='Retain local edits' and first['sync']=='queued'
    inv.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
print('PASS 315-invoice download: one background durable write, retained local edits, no GUI-thread persistence')

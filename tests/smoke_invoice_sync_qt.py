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
with tempfile.TemporaryDirectory() as d:
    d=Path(d);v=Vault(d/'vault.dpapi');v.update(credentials=CREDS,tokens=pair());p=Preferences(d/'settings.json');p.save(reminders=False,standalone=False)
    server=InvoiceServer();b=Controller(FreshBooks(v,server),v,p,root/'src/assets',root/'src/main.pyw',False,tray=False);b.offline.probe=lambda:True;b.sync_timer.stop();b.start();settle(b)
    inv=b.invoices;inv.activate();inv.download();settle(b);assert inv.state['clients']
    from unittest.mock import patch
    with patch.object(inv.store,'data',side_effect=AssertionError('UI must not copy the full billing cache')):
        snapshot=inv.state
    original=inv.state['clients'][0]['name'];snapshot['clients'][0]['name']='Changed returned view'
    assert inv.state['clients'][0]['name']==original,'Returned UI data must not mutate stored snapshots'
    inv.newInvoice();inv.field('client','123');inv.line(0,'name','Test');inv.line(0,'rate','100');inv.save();assert inv.draft['sync']=='queued'
    inv.sync();settle(b);assert inv.draft['sync']=='synced' and len(server.invoices)==1
    inv.download();settle(b)
    assert inv.state['seller']['name']=='Connected Studio'
    assert inv.state['seller']['email']=='billing@example.invalid'
    assert inv.state['seller']['logo'].startswith('data:image/png;base64,')
    assert inv.store.data()['caches'][inv.namespace()]['seller']['logo']==inv.state['seller']['logo']
    assert not inv.store.data()['seller'].get('logo'), 'Connected branding must not overwrite standalone business details'
    inv.line(0,'description','Updated');inv.save();inv.sync();settle(b)
    assert [x[0] for x in server.invoice_calls]==['POST','PUT']
    inv.line(0,'description','Local edit');inv.save();server.invoices[1]['version']='external-change';inv.sync();settle(b)
    assert inv.draft['sync']=='conflict' and len(server.invoice_calls)==2
    inv.review('keep');inv.back();inv.newInvoice();inv.line(0,'name','Ambiguous');inv.line(0,'rate','80');inv.save();server.fail_invoice=True;inv.sync();settle(b)
    assert inv.draft['sync']=='review' and len(server.invoice_calls)==3
    inv.sync();settle(b);assert len(server.invoice_calls)==3,'An ambiguous create must not retry automatically'
    assert not any('action_email' in call[1]['invoice'] for call in server.invoice_calls)
    inv.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close();b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True)
print('PASS: fake-provider invoice download, explicit create/update, conflict protection, durable ambiguous-write review and no automatic duplicate retry or sending.')

"""Exercise connected billing writes, conflicts and lost responses using a fake provider."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from urllib.parse import parse_qs, urlsplit

import _paths
from PySide6.QtWidgets import QApplication

from freshtray.api import ApiError, FreshBooks
from freshtray.billing_features import RESOURCES
from freshtray.qt_app import Controller
from freshtray.storage import Preferences, Vault
from test_core import CREDS, pair
from test_offline import Server


class BillingServer(Server):
    def __init__(self):
        super().__init__()
        self.tables = {kind: {} for kind in RESOURCES}
        self.tables['clients'][123] = dict(userid=123, organization='Studio', updated='initial', vis_state=0)
        self.invoices = {}
        self.linked = {}
        self.writes = []
        self.offline = False
        self.payment_preflight_down = False
        self.lost_payment = False

    def __call__(self, method, path, body=None, token=None):
        if self.offline:
            raise ApiError('Offline', uncertain=True)
        url = urlsplit(path)
        query = parse_qs(url.query)
        if '/items/items' in url.path:
            return self.result({'items': [], 'pages': 1})
        if '/systems/systems' in url.path:
            return self.result({'system': {'name':'Test Studio', 'currency_code':'USD'}})
        if '/invoices/invoices' in url.path:
            suffix = url.path.split('/invoices/invoices', 1)[1].strip('/')
            if method=='GET':
                if suffix and self.payment_preflight_down:
                    raise ApiError('Invoice check timed out before any write', uncertain=True)
                result = {'invoice': self.invoices[int(suffix)]} if suffix else {'invoices':list(self.invoices.values()),'pages':1}
                return self.result(result)
            key = int(suffix) if suffix else 501
            self.writes.append(('invoices',method))
            payload = body['invoice']
            self.invoices[key] = dict(payload,id=key, invoiceid=key, invoice_number='INV-501', paid={'amount':'0'},
                                      amount={'amount':'110.00'}, display_status='sent', outstanding={'amount':'110.00'})
            self.linked[payload['estimateid']] = key
            return self.result({'invoice':self.invoices[key]})
        for kind, (resource, singular, ids) in RESOURCES.items():
            if '/' + resource not in url.path:
                continue
            suffix = url.path.split('/'+resource, 1)[1].strip('/')
            table = self.tables[kind]
            if method=='GET':
                if suffix:
                    record = deepcopy(table[int(suffix)])
                    if kind=='estimates' and int(suffix) in self.linked:
                        record['invoices'] = [self.linked[int(suffix)]]
                    return self.result({singular:record})
                rows = list(table.values())
                for field in ('vis_state','invoiceid'):
                    if f'search[{field}]' in query:
                        rows = [row for row in rows if str(row.get(field,0))==query[f'search[{field}]'][0]]
                return self.result({kind:rows, 'pages':1})
            self.writes.append((kind,method))
            ident = int(suffix) if suffix else max(table, default=0)+1
            record = dict(table.get(ident,{}), **deepcopy(body[singular]))
            record.update({ids[0]:ident,'updated':str(len(self.writes))})
            if kind=='estimates':
                record.setdefault('estimate_number','EST-001')
                record.setdefault('status',1)
            table[ident] = record
            if kind=='payments':
                assert body[singular]['send_client_notification'] is False
                invoice = self.invoices[record['invoiceid']]
                paid = sum((Decimal(row['amount']['amount']) for row in table.values() if not row.get('vis_state')), Decimal(0))
                invoice['paid']['amount'] = str(paid)
                invoice['outstanding']['amount'] = str(Decimal('110')-paid)
                invoice['display_status'] = 'paid' if paid==110 else 'partial' if paid else 'sent'
                if self.lost_payment:
                    raise ApiError('Lost after provider applied it', uncertain=True)
            return self.result({singular:record})
        return super().__call__(method,path,body,token)

    @staticmethod
    def result(values):
        return {'response':{'result':deepcopy(values)}}


app = QApplication([])
root = Path(__file__).resolve().parents[1]
def settle(owner):
    until=time.monotonic()+10
    while owner.state['busy'] or owner.invoices.busy:
        app.processEvents()
        time.sleep(.006)
        assert time.monotonic()<until, 'Billing worker did not settle'


with TemporaryDirectory() as folder:
    folder=Path(folder)
    vault=Vault(folder/'vault.dpapi')
    vault.update(credentials=CREDS,tokens=pair())
    prefs=Preferences(folder/'settings.json')
    prefs.save(reminders=False,standalone=False)
    server=BillingServer()
    owner=Controller(FreshBooks(vault,server),vault,prefs,root/'src/assets',root/'src/main.pyw',False,tray=False)
    owner.offline.probe=lambda: not server.offline
    owner.sync_timer.stop()
    owner.start()
    settle(owner)
    bill=owner.invoices
    tools=bill.billingTools
    tools.refresh('clients')
    settle(owner)
    assert tools.state['clients'][0]['id']=='123', tools.notice
    server.offline=True
    tools.saveClient('',dict(company='New Account', email='customer@example.invalid'))
    assert len(Vault(folder/'vault.dpapi').get('billing_v1')['billing_tools'][bill.namespace()]['queue'])==1
    tools.saveClient('',dict(company='New Account', email='customer@example.invalid'))
    assert len(tools.state['pending'])==1 and not server.writes
    tools.sync()
    settle(owner)
    assert tools.state['pending'][0]['status']=='queued' and not server.writes
    server.offline=False
    tools.sync()
    settle(owner)
    client=next(row for row in tools.state['clients'] if row['name']=='New Account')
    assert not tools.state['pending'], tools.notice
    tools.archiveClient(client['id'],True)
    owner.answer(True)
    tools.sync()
    settle(owner)
    assert server.tables['clients'][int(client['id'])]['vis_state']==2
    tools.archiveClient(client['id'],False)
    tools.sync()
    settle(owner)
    assert server.tables['clients'][int(client['id'])]['vis_state']==0
    tools.saveClient(client['id'],dict(company='Pending edit'))
    server.tables['clients'][int(client['id'])]['updated']='external'
    writes=len(server.writes)
    tools.sync()
    settle(owner)
    assert len(server.writes)==writes and tools.state['pending'][0]['status']=='review'
    tools.discard(tools.state['pending'][0]['id'])
    owner.answer(True)
    tools.refresh('clients')
    settle(owner)

    tools.openEstimate('')
    tools.estimateField('client',client['id'])
    tools.estimateLine(0,'name','Consulting')
    tools.estimateLine(0,'rate','100.00')
    tools.estimateLine(0,'tax','10')
    tools.estimateAction('sync')
    tools.sync()
    settle(owner)
    assert tools.active_estimate()['remote_id']=='1' and not tools.state['pending'], tools.notice
    tools.estimateAction('convert')
    owner.answer(True)
    settle(owner)
    bill.save()
    bill.sync()
    settle(owner)
    assert bill.draft['remote']['id']==501 and bill.draft['source_estimate_remote']=='1', bill.problem
    assert server.invoices[501]['estimateid']==1 and len(server.invoices)==1
    inv_id=bill.draft['id']
    tools.estimateAction('convert')
    assert bill.draft['id']==inv_id and len(server.invoices)==1

    values=dict(amount='40.00', date=date.today().isoformat(), method='Cash', note='QA')
    # The automatic payment path must leave unrelated manual changes queued.
    tools.saveClient('', dict(company='Unsubmitted customer'))
    server.offline=True
    assert tools.recordPayment('',values,False)
    settle(owner)
    assert tools.state['pending'] and not tools.state['payments']
    assert tools.state['currentPaymentPending'] and 'automatically' in tools.state['notice']
    saved=Vault(folder/'vault.dpapi').get('billing_v1')['billing_tools'][bill.namespace()]['queue']
    assert any(job['kind']=='payments' and job['status']=='queued' and job['automatic'] for job in saved)
    writes = len(server.writes)
    assert not tools.recordPayment('',values,False)
    assert len(server.writes)==writes
    server.offline=False
    server.payment_preflight_down=True
    tools.sync_payments()
    settle(owner)
    assert any(job['kind']=='payments' and job['status']=='queued' for job in tools.state['pending'])
    assert len(server.writes)==writes
    server.payment_preflight_down=False
    tools.payment_timer.setInterval(30)
    settle(owner)
    until=time.monotonic()+5
    while tools.state['currentPaymentPending']:
        app.processEvents()
        time.sleep(.006)
        assert time.monotonic()<until, 'Queued payment did not restart automatically'
    tools.payment_timer.setInterval(15000)
    settle(owner)
    assert bill.state['totals']['balance']=='70.00' and len(tools.state['payments'])==1, tools.notice
    assert len(server.writes)==writes+1 and server.writes[-1]==('payments','POST')
    pending=tools.state['pending']
    assert len(pending)==1 and pending[0]['kind']=='clients'
    tools.discard(pending[0]['id'])
    owner.answer(True)
    record=tools.state['payments'][0]['id']
    assert tools.recordPayment(record,dict(values,amount='50.00'),False)
    settle(owner)
    assert bill.state['totals']['balance']=='60.00'
    assert tools.recordPayment(record,{},True)
    settle(owner)
    assert bill.state['totals']['balance']=='110.00' and not tools.state['payments']
    tools.saveClient('', dict(company='Still unsubmitted'))
    tools.enqueue('payments', 'Previously queued payment', '', dict(
        invoiceid=501, date=values['date'], type='Cash', note='Legacy QA',
        amount=dict(amount='40.00',code='USD')), invoice_id='501', method='Cash')
    tools.sync_payments()
    settle(owner)
    assert not tools.state['payments'], 'A legacy payment synced before confirmation'
    tools.confirmLegacyPaymentSync('501')
    owner.answer(True)
    settle(owner)
    pending=tools.state['pending']
    assert len(pending)==1 and pending[0]['kind']=='clients'
    tools.discard(pending[0]['id'])
    owner.answer(True)
    assert tools.recordPayment(tools.state['payments'][0]['id'],{},True)
    settle(owner)
    assert bill.state['totals']['balance']=='110.00' and not tools.state['payments']
    server.lost_payment=True
    assert tools.recordPayment('',values,False)
    settle(owner)
    assert tools.state['pending'][0]['status']=='review'
    count=len(server.writes)
    tools.sync_payments()
    settle(owner)
    assert len(server.writes)==count, 'Ambiguous payment was resent'
    tools.refresh('payments')
    settle(owner)
    assert len(tools.state['payments'])==1 and bill.state['totals']['balance']=='70.00'
    bill.close()
    owner._updater.close()
    owner.local_executor.shutdown(wait=True)
    owner.executor.shutdown(wait=True)

print('PASS: connected fixture clients, archive/restore, offline queue, conflict, estimates, linked conversion, payment history and uncertain-write review.')

import threading
import unittest
from copy import deepcopy
from datetime import date
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from urllib.parse import urlsplit,parse_qs
import _paths
from freshtray.billing import BillingStore,blank_invoice,blank_line,totals,validate,import_lines,mailto,email_file,invoice_html
from freshtray.local_provider import LocalProvider
from freshtray.invoice_api import InvoiceAPI,normalized,signature
from freshtray.api import OAuthAttempt,ApiError
from test_core import MemoryVault,CREDS
from freshtray.model import entry_payload

class Store(MemoryVault):
    def __init__(self):super().__init__();self.lock=threading.RLock()

class BillingTests(unittest.TestCase):
    def setUp(self):
        self.vault=Store();self.store=BillingStore(self.vault)
        self.client=self.store.add('clients',dict(name='Example Client',email='client@example.invalid',address='Test address'))
        self.inv=blank_invoice(str(self.client['id']));self.inv['lines'][0].update(name='Editing',qty='2.5',rate='125.00',tax='8')

    def test_decimal_totals_discount_and_two_taxes(self):
        self.inv['discount']='10';t=totals(self.inv)
        self.assertEqual(t['subtotal'],'312.50');self.assertEqual(t['discount'],'31.25');self.assertEqual(t['tax'],'22.50');self.assertEqual(t['total'],'303.75')
        self.inv['lines'][0].update(tax2='10',compound=True)
        self.assertEqual(totals(self.inv)['tax'],'52.88')

    def test_invalid_money_dates_quantities_currency(self):
        for key,value in [('qty','0'),('qty','NaN'),('rate','-1'),('rate','0.001'),('tax','Infinity')]:
            inv=deepcopy(self.inv);inv['lines'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate(inv)
        for key,value in [('date','bad'),('due','1900-01-01'),('currency','US'),('discount','101'),('number','bad\nheader')]:
            inv=deepcopy(self.inv);inv[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(inv)

    def test_atomic_numbering_duplicate_and_profile_separation(self):
        one=self.store.put('local',self.inv);self.assertEqual(one['number'],'FT-000001')
        two=blank_invoice(str(self.client['id']));two['lines'][0]['name']='Item'
        self.assertEqual(self.store.put('local',two)['number'],'FT-000002')
        third=deepcopy(two);third['id']='new';third['number']=one['number']
        with self.assertRaises(ValueError):self.store.put('local',third)
        self.assertEqual(self.store.rows('fb:1:account'),[])

    def test_failed_storage_does_not_publish_success(self):
        previous=deepcopy(self.vault.data)
        def fail(**kw):raise OSError('disk full')
        self.vault.update=fail
        with self.assertRaises(OSError):self.store.put('local',self.inv)
        self.assertEqual(self.vault.data,previous)

    def test_duplicate_time_reservation_and_archive_release(self):
        provider=LocalProvider(self.vault);row=provider.submit(-1001,entry_payload(self.client['id'],date.today().isoformat(),'1:00','Work',True,-1001))
        self.inv['lines'][0]['sources']=['time:'+str(row['id'])]
        saved=self.store.put('local',self.inv)
        self.assertTrue(provider.get_entry(-1001,row['id'])['billed'])
        other=deepcopy(saved);other.update(id='other',number='other')
        with self.assertRaises(ValueError):self.store.put('local',other)
        self.store.patch('local',saved['id'],deleted=True)
        self.assertFalse(provider.get_entry(-1001,row['id'])['billed'])
        self.store.put('local',other)

    def test_client_and_project_scope_validation(self):
        second=self.store.add('clients',dict(name='Second'))
        project=self.store.add('projects',dict(name='Film',client_id=str(self.client['id'])))
        with self.assertRaises(ValueError):self.store.add('expenses',dict(name='Parking',client_id=str(second['id']),project_id=str(project['id']),date=date.today().isoformat(),amount='2'))
        updated=self.store.add('clients',dict(id=self.client['id'],name='Renamed',email='client@example.invalid'))
        self.assertEqual(updated['id'],self.client['id']);self.assertEqual(len(self.store.data()['clients']),2)

    def test_mail_encoding_headers_and_attached_pdf(self):
        self.inv['number']='FT-1';self.inv['note']='<img src="https://invalid"> & note'
        seller=dict(name='Example & Studio',email='me@example.invalid',address='Test')
        client=dict(name='Sample',email='client+test@example.invalid')
        uri=mailto(self.inv,client,seller);query=parse_qs(urlsplit(uri).query)
        self.assertIn('Example & Studio',query['subject'][0]);self.assertIn('Attach the exported',query['body'][0]);self.assertNotIn('attach=',uri)
        msg=BytesParser(policy=policy.default).parsebytes(email_file(self.inv,client,seller,b'%PDF-test'))
        self.assertEqual(msg['X-Unsent'],'1');self.assertEqual(next(msg.iter_attachments()).get_payload(decode=True),b'%PDF-test')
        self.assertIn('&lt;img',invoice_html(self.inv,client,seller));self.assertNotIn('<img',invoice_html(self.inv,client,seller))
        with self.assertRaises(ValueError):mailto(self.inv,dict(client,email='bad\r\nBcc:x@example.invalid'),seller)

    def test_scopes_opt_in(self):
        plain=parse_qs(urlsplit(OAuthAttempt(CREDS).url()).query)['scope'][0]
        invoice=parse_qs(urlsplit(OAuthAttempt(dict(CREDS,invoice_access=True)).url()).query)['scope'][0]
        self.assertNotIn('user:invoices:write',plain);self.assertIn('user:invoices:write',invoice);self.assertIn('user:expenses:read',invoice)

    def test_bulk_rate_formats_filters_expenses_and_exact_total(self):
        times=[dict(id=1,client_id='1',date='2026-11-01',project_id='',project='No project',service='Editing',member='Sample',duration=5400,rate='100'),dict(id=2,client_id='1',date='2026-11-02',project_id='',project='No project',service='Editing',member='Sample',duration=3600,rate='150')]
        expenses=[dict(id=3,client_id='1',date='2026-11-02',project_id='',name='Parking',amount='24')]
        options=dict(client='1',projects=[''],rate='80',expenses='all',includes=['date'],format='detailed')
        for mode in ['detailed','grouped','simple']:
            lines=import_lines(times,expenses,dict(options,format=mode))
            self.assertEqual(sum(Decimal(l['qty'])*Decimal(l['rate']) for l in lines),Decimal('224'))
        zero=import_lines(times,expenses,dict(options,rate='0'))
        self.assertEqual(sum(Decimal(l['qty'])*Decimal(l['rate']) for l in zero),Decimal('24'))
        self.assertEqual(len(import_lines(times,expenses,options,used=['time:1','expense:3'])),1)
        self.assertEqual(import_lines(times,expenses,dict(options,projects=[],expenses='selected')),[])
        with self.assertRaises(ValueError):import_lines(times,expenses,dict(options,rate='-1'))
        with self.assertRaises(ValueError):import_lines(times,expenses,dict(options,**{'from':'2026-12-01','to':'2026-11-01'}))

    def test_mixed_and_fractional_rates_preserve_amounts(self):
        times=[dict(id=1,client_id='1',date='2026-11-01',project_id='',duration=61,rate='125'),dict(id=2,client_id='1',date='2026-11-02',project_id='',duration=91,rate='150')]
        rows=import_lines(times,[],dict(client='1',projects=[''],format='simple'))
        expected=(Decimal(61)/3600*125+Decimal(91)/3600*150).quantize(Decimal('.01'))
        self.assertEqual(Decimal(rows[0]['qty'])*Decimal(rows[0]['rate']),expected)

    def test_local_timer_receipt_is_atomic_and_idempotent(self):
        import uuid
        provider=LocalProvider(self.vault);key=str(uuid.uuid4());payload=entry_payload(self.client['id'],date.today().isoformat(),'0:02','Timer',True,-1001)
        first=provider.submit_timer(-1001,payload,key);second=LocalProvider(self.vault).submit_timer(-1001,payload,key)
        self.assertEqual(first['id'],second['id']);self.assertEqual(len(self.store.data()['time']),1)
        self.assertEqual(provider.timer_submission_state(key),'saved')
        changed=deepcopy(payload);changed['time_entry']['duration']=200
        with self.assertRaises(ValueError):provider.submit_timer(-1001,changed,key)
        provider.forget_timer_receipt(key);self.assertEqual(provider.timer_submission_state(key),'absent')

    def test_invoice_party_snapshot_and_currency_guard(self):
        self.store.mutate(lambda d:d['seller'].update(name='Original business',currency='USD'))
        saved=self.store.put('local',self.inv)
        self.store.add('clients',dict(id=self.client['id'],name='Renamed client'))
        self.assertEqual(saved['client_snapshot']['name'],'Example Client')
        self.assertEqual(saved['seller_snapshot']['name'],'Original business')
        with self.assertRaises(ValueError):import_lines([], [dict(id=7,client_id='1',date='2026-11-01',name='Cost',amount='10',currency='CAD')],dict(client='1',currency='USD',projects=[],expenses='all'))

    def test_server_total_mismatch_blocks_inaccurate_export(self):
        inv=deepcopy(self.inv);inv['sync']='synced';inv['remote']={'raw':{'amount':{'amount':'1.00'}}}
        with self.assertRaises(ValueError):validate(inv)

    def test_new_scope_flags_are_not_posted_as_oauth_fields(self):
        from freshtray.api import FreshBooks,DEFAULT_REDIRECT
        posted=[]
        def server(method,path,body=None,token=None):
            posted.append(body);return dict(access_token='fake',refresh_token='fake-refresh',expires_in=3600)
        attempt=OAuthAttempt(dict(CREDS,invoice_access=True))
        FreshBooks(self.vault,server).connect(attempt,DEFAULT_REDIRECT+'?state='+attempt.state+'&code=fake')
        self.assertNotIn('invoice_access',posted[0]);self.assertTrue(self.vault.get('credentials')['invoice_access'])

class InvoiceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.raw=dict(id=22,customerid=4,invoice_number='001',create_date='2026-11-01',due_date='2026-12-01',currency_code='USD',version='v1',lines=[dict(lineid=12,name='Work',description='Keep',qty='1',unit_cost=dict(amount='50.00',code='USD'),modern_time_entries=[77],taxName1='GST',taxAmount1=5,retainer_id=9)])
        self.calls=[]
        raw=self.raw
        class API:
            def request(_,method,path,body=None):
                self.calls.append((method,path,body));return {'response':{'result':{'invoice':deepcopy(raw)}}}
        self.adapter=InvoiceAPI(API(),dict(id=1,account_id='test/account'))

    def test_preserves_all_lines_ids_links_and_tax(self):
        inv=normalized(self.raw);inv['lines'][0]['description']='Edited'
        payload=self.adapter.payload(inv)['invoice'];line=payload['lines'][0]
        self.assertEqual(line['lineid'],12);self.assertEqual(line['retainer_id'],9);self.assertEqual(line['modern_time_entries'],[77]);self.assertEqual(line['taxAmount1'],'5')
        self.assertNotIn('action_email',payload);self.assertEqual(len(payload['lines']),1)
        self.adapter.write(inv);self.assertEqual(self.calls[-1][0],'PUT')

    def test_conflicting_version_never_writes(self):
        inv=normalized(self.raw);self.raw['version']='v2'
        with self.assertRaises(ValueError):self.adapter.write(inv)
        self.assertTrue(all(c[0]=='GET' for c in self.calls))

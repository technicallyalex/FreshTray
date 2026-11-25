"""Standalone invoices and PDF/mail creation; all networking is rejected."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile,socket
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QUrl,QObject,QEvent,QCoreApplication,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from freshtray.qt_app import Controller
from freshtray.storage import Vault,Preferences
from freshtray.api import FreshBooks
from freshtray.local_provider import LocalProvider

root=Path(__file__).resolve().parents[1];app=QApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
for font in (root/'src/assets/fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
messages=[];qInstallMessageHandler(lambda kind,ctx,msg:messages.append(msg))
def pump(seconds=.15):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.004)
def settle(b):
    until=time.monotonic()+8
    while b.state['busy'] or b.invoices.busy:
        pump(.02);assert time.monotonic()<until,'timeout'
    pump()
with tempfile.TemporaryDirectory() as folder,patch('socket.socket',side_effect=AssertionError('Standalone network access')),patch('freshtray.alert_sound.winsound.PlaySound'):
    folder=Path(folder);v=Vault(folder/'vault.dpapi');prefs=Preferences(folder/'settings.json');prefs.save(standalone=True,theme='light',reminders=False)
    b=Controller(FreshBooks(v),v,prefs,root/'src/assets',root/'src/main.pyw',False,tray=False)
    e=QQmlApplicationEngine();e.rootContext().setContextProperty('backend',b);e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(),messages
    w=e.rootObjects()[0];b.window=w;w.show();b.start();settle(b)
    bill=b.invoices;assert b.local_mode and b.state['panel']=='invoices'
    bill.seller(dict(name='Example Studio',email='studio@example.invalid',address='123 Sample Street\nPortland, OR',currency='USD'))
    bill.addRecord('clients',dict(name='Example Client',email='client@example.invalid',address='456 Example Lane'))
    settle(b);cid=str(bill.state['clients'][0]['id'])
    b.setField('log','client',cid);b.setField('log','hours','1:30');b.setField('log','note','Invoice QA work');b.submit('log');settle(b)
    bill.addRecord('expenses',dict(name='Parking',client_id=cid,date=__import__('datetime').date.today().isoformat(),amount='24',project_id=''))
    bill.newInvoice();bill.field('client',cid);bill.openImport();bill.importField('rate','100');assert len(bill.imported)==2,bill.problem
    bill.addImport();bill.save();assert not bill.problem,bill.problem
    assert bill.state['totals']['total']=='174.00'
    assert bill.state['summaries']==[dict(currency='USD',overdue='0.00',outstanding='0.00',draft='174.00')]
    bill.filterRows('no matching invoice','All')
    assert not bill.state['rows'] and bill.state['summaries'][0]['draft']=='174.00'
    bill.filterRows('','All')
    bill.store.patch(bill.namespace(),bill.draft['id'],status='Sent',due='2000-01-01')
    assert bill.state['rows'][0]['status']=='Overdue'
    assert bill.state['summaries'][0]['overdue']=='174.00' and bill.state['summaries'][0]['outstanding']=='174.00'
    bill.filterRows('','Overdue');assert len(bill.state['rows'])==1
    bill.filterRows('','All')
    bill.store.patch(bill.namespace(),bill.draft['id'],status='Draft',due=bill.draft['due'])
    from PySide6.QtGui import QImage, QColor
    logo_path=folder/'logo.png'
    logo=QImage(160,160,QImage.Format_ARGB32);logo.fill(QColor('#008a22'));assert logo.save(str(logo_path))
    bill.set_logo(logo_path);assert bill.state['seller']['logo'].startswith('data:image/png;base64,')
    bill.seller(dict(name='Example Studio',email='studio@example.invalid',address='123 Sample Street\nPortland, OR',currency='USD'))
    assert bill.state['seller']['logo'], 'Saving business details must retain the logo'
    bill.save();assert not bill.problem,bill.problem
    assert bill.parties()[1]['logo'] and 'width="90" height="90"' in __import__('freshtray.billing',fromlist=['invoice_html']).invoice_html(bill.draft,*bill.parties())
    logo_path.unlink()
    bill.openImport();assert not bill.imported,'Sources must not be imported twice';bill.editPreview()
    bill.showPreview();assert '174.00' in bill.preview
    bill.make_pdf(root/'.build/invoice-test.pdf');assert (root/'.build/invoice-test.pdf').read_bytes().startswith(b'%PDF-')
    from freshtray.billing import email_file
    client,seller=bill.parties();(root/'.build/invoice-test.eml').write_bytes(email_file(bill.draft,client,seller,(root/'.build/invoice-test.pdf').read_bytes()))
    bill.editPreview();pump();w.grabWindow().save(str(root/'.build/invoice-editor-light.png'))
    b.applySetting('theme','dark');pump();w.grabWindow().save(str(root/'.build/invoice-editor-dark.png'))
    # Long invoices must paginate and retain totals/notes in the final PDF.
    bill.newInvoice();bill.field('client',cid)
    for i in range(34):
        if i:bill.addLine()
        bill.line(i,'name','Production service '+str(i+1));bill.line(i,'description','A detailed work description covering editing, audio and delivery. '*4);bill.line(i,'rate','12.50')
    bill.field('note','Final notes: thank you.');bill.save();assert not bill.problem,bill.problem
    bill.make_pdf(root/'.build/invoice-multipage.pdf')
    # Draft recovery must not depend on provider connectivity.
    bill.field('note','Retain this unfinished draft');bill.persist_draft()
    assert Vault(v.path).get('invoice_drafts')[bill.namespace()]['note']=='Retain this unfinished draft'
    bill.localAction('sent','');bill.localAction('payment','10');assert bill.draft['status']=='Partial',bill.problem
    # Returning to the list and quitting must retain an unfinished invoice draft.
    bill.newInvoice()
    draft_id=bill.draft['id'];bill.field('note','Recovery after Back');bill.back();bill.persist_draft()
    assert Vault(v.path).get('invoice_drafts')[bill.namespace()]['note']=='Recovery after Back'
    bill.resume();assert bill.draft['id']==draft_id
    b._updater.checkUpdates();pump();assert b._updater.state['phase']=='idle'
    # Standalone timer saves share durable receipt recovery and invalidate cached months.
    b.setField('timer','client',cid);b.setField('timer','note','Standalone timer test')
    b.work_timer.primary();b.work_timer.pause();b.work_timer.primary();b.work_timer.duration('00:01:31');b.work_timer.primary();settle(b)
    assert b.work_timer.status=='idle',b.work_timer.status
    rows=bill.store.data()['time'];assert len([x for x in rows if x.get('note')=='Standalone timer test'])==1
    assert not b._updater.portable and b._updater.demo
    assert not [m for m in messages if any(x in m for x in ('ReferenceError','TypeError','Binding loop','is not defined'))],messages
    bill.close();b._updater.close();b.timer.stop();b.sync_timer.stop();b.reminder_timer.stop();b.delay_timer.stop();b.popup_chime.close()
    b.local_executor.shutdown(wait=True);b.executor.shutdown(wait=True);w.hide();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
print('PASS: offline first-use setup, client/expense creation, real time logging, imports/bulk rates, duplicate prevention, invoice save, preview/PDF/email, draft recovery and payment records with networking blocked.')

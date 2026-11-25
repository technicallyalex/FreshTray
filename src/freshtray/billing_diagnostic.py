"""Packaged billing smoke checks with an isolated profile and sanitized results."""
from pathlib import Path
import faulthandler
import json
import time

from PySide6.QtCore import QObject, QMetaObject, Q_ARG, QPointF, Qt, QTimer, qInstallMessageHandler
from PySide6.QtGui import QWindow
from PySide6.QtTest import QTest

from .billing import invoice_html, totals
from .storage import Vault


def run_billing_check(app, owner, window, folder, live):
    folder.mkdir(parents=True, exist_ok=True)
    log = (folder / 'billing-qa.log').open('w', encoding='utf-8', buffering=1)
    bill = owner.invoices
    tools = bill.billingTools
    errors = []
    started = time.monotonic()
    timer = QTimer(app)
    timer.setInterval(100)
    faulthandler.dump_traceback_later(25, file=log)
    def message(kind, context, value):
        if any(needle in value for needle in ('ReferenceError', 'TypeError', 'Binding loop', 'recursive rearrange')):
            errors.append(value)
            log.write('QML error: ' + value + '\n')
    qInstallMessageHandler(message)
    def item_named(parent, name):
        if parent.objectName() == name:
            return parent
        for child in parent.childItems():
            match = item_named(child, name)
            if match:
                return match
        return None
    def click(name):
        item = item_named(window.contentItem(), name)
        assert item is not None and item.isVisible(), 'Missing control ' + name
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    def tab_metrics():
        return tuple((item.width(), item.height(), item.property('text')) for item in
                     (item_named(window.contentItem(), page + 'Tab') for page in
                      ('log','month','timer','invoices','estimates','clients','settings')))
    dimensions = None
    def visit(name):
        nonlocal dimensions
        if dimensions is None:
            dimensions = tab_metrics()
        assert tab_metrics() == dimensions, 'Tab dimensions or labels changed across panels'
        click(name + 'Tab')
        assert owner.state['panel'] == name, 'Tab did not select ' + name
    def check_client_navigation():
        def controls(item):
            yield item
            for child in item.childItems():
                yield from controls(child)
        for name in ('invoicesPanel', 'estimatesPanel'):
            panel = item_named(window.contentItem(), name)
            assert panel is not None
            assert not any(item.property('text') == 'Clients' for item in controls(panel)), 'Duplicate Clients action'
        assert item_named(window.contentItem(), 'clientsTab').isVisible(), 'Clients tab is missing'
    def finish(error=None):
        timer.stop()
        qInstallMessageHandler(None)
        faulthandler.cancel_dump_traceback_later()
        if live:
            log.write('LIVE_API ' + json.dumps(owner.remote_api.transport.summary()) + '\n')
        log.write(('FAIL ' + type(error).__name__ + ': ' + str(error) if error else 'PASS') + '\n')
        log.close()
        if error:
            app.exit(2)
        else:
            owner.requestQuit()
    def standalone():
        assert owner.local_mode, 'Expected an isolated standalone profile'
        check_client_navigation()
        assert window.flags() & Qt.WindowType_Mask == Qt.Window
        foreground = QWindow()
        foreground.show()
        foreground.requestActivate()
        yield 'Ordinary taskbar window while another window has focus'
        assert window.isVisible() and window.visibility() != QWindow.Visibility.Minimized
        foreground.close()
        bill.seller(dict(name='QA Studio', email='studio@example.invalid', address='Example district', currency='USD'))
        visit('clients')
        tools.saveClient('', dict(company='QA Client', first='Casey', email='client@example.invalid', phone='555-0100', street='123 Example'))
        client = str(tools.state['clients'][0]['id'])
        tools.saveClient(client, dict(company='QA Client renamed', email='client@example.invalid'))
        yield 'Client creation and edit'
        visit('estimates')
        click('newEstimate')
        tools.estimateLine(0, 'name', 'Design service')
        tools.estimateLine(0, 'rate', '125.00')
        tools.estimateLine(0, 'qty', '2')
        tools.estimateField('discount','10')
        tools.estimateLine(0, 'tax', '10')
        yield 'Estimate editor loaded'
        tools.estimateAction('save')
        tools.estimateAction('sent')
        tools.estimateAction('accepted')
        tools.estimateAction('preview')
        estimate = tools.active_estimate()
        assert estimate['status']=='Accepted' and totals(estimate)['total']=='247.50', tools.notice
        assert 'Estimate Number' in tools.preview and 'Amount Due' not in tools.preview
        pdf = folder / 'qa-estimate.pdf'
        bill.render_pdf(pdf, invoice_html(estimate, *tools.estimate_parties(estimate)))
        assert pdf.read_bytes().startswith(b'%PDF')
        yield 'Estimate preview and PDF'
        tools.estimateAction('convert')
        yield 'Estimate conversion confirmation'
        click('confirmContinue')
        assert owner.state['panel']=='invoices' and bill.draft, tools.notice
        invoice_id = bill.draft['id']
        assert totals(bill.draft)['total']=='247.50'
        yield 'Estimate conversion opened invoice editor'
        visit('estimates')
        yield 'Reopened estimate'
        tools.estimateAction('convert')
        assert len(bill.store.rows('local'))==1 and bill.draft['id']==invoice_id
        yield 'Estimate conversion and repeat conversion'
        click('invoicePayments')
        yield 'Opened invoice payments'
        click('paymentCalendar')
        yield 'Opened the payment calendar'
        picker = window.findChild(QObject, 'paymentDatePicker')
        assert picker and picker.property('opened'), 'Received date calendar did not open'
        assert QMetaObject.invokeMethod(picker, 'picked', Qt.DirectConnection, Q_ARG(str, '2024-01-03'))
        field = item_named(window.contentItem(), 'paymentReceivedDate')
        assert field and field.property('text') == '2024-01-03', 'Calendar date did not reach the payment form'
        QTest.keyClick(window, Qt.Key_Escape)
        yield 'Selected a payment date'
        args = dict(date=field.property('text'), method='Cash', note='QA receipt')
        tools.recordPayment('', dict(args, amount='100.00'), False)
        assert bill.state['totals']['balance']=='147.50', tools.notice
        assert tools.state['payments'][0]['date']=='2024-01-03'
        tools.recordPayment('', dict(args, amount='147.50'), False)
        assert bill.draft['status']=='Paid' and len(tools.state['payments'])==2, tools.notice
        first = tools.state['payments'][0]['id']
        tools.recordPayment(first, dict(args, amount='75.00'), False)
        assert bill.draft['status']=='Partial' and bill.state['totals']['balance']=='25.00'
        tools.recordPayment(first, {}, True)
        assert bill.state['totals']['balance']=='100.00'
        disk = Vault(folder / 'vault.dpapi').get('billing_v1')
        assert len(disk['books']['local'][0]['payments'])==1
        yield 'Payment window, partial/full payment, correction, removal, and durable reload'
        QTest.keyClick(window, Qt.Key_Escape)
        yield 'Closed payment history'
        tools.archiveClient(client, True)
        yield 'Client archive confirmation'
        click('confirmContinue')
        assert not bill.catalogs()['clients'] and bill.parties()[0]['name']=='QA Client renamed'
        tools.archiveClient(client, False)
        assert bill.catalogs()['clients']
        yield 'Client archive and restore preserve invoice history'
    def connected():
        assert not owner.local_mode and owner.state['catalogReady'], 'Expected a connected business'
        visit('settings')
        yield 'Opened Settings'
        click('connectionSectionTab')
        yield 'Opened FreshBooks connection'
        click('refreshClients')
        yield 'Clients API'
        assert tools.state['clients'] and not tools.errors.get('clients'), 'Live clients unavailable'
        click('refreshEstimates')
        yield 'Estimates API or permission handoff'
        if tools.errors.get('estimates'):
            assert 'permissions' in tools.errors['estimates'], 'Unexpected estimates read failure'
        click('refreshPayments')
        yield 'Account payment history API or permission handoff'
        if tools.errors.get('allPayments'):
            assert 'permissions' in tools.errors['allPayments'], 'Unexpected account payments read failure'
        click('refreshInvoices')
        yield 'Invoices API'
        visit('invoices')
        yield 'Opened Invoices'
        row = next(row for row in bill.store._snapshot()['books'][bill.namespace()] if row['sync']=='synced')
        bill.openInvoice(row['id'])
        yield 'Real invoice detail'
        click('invoicePayments')
        yield 'Payments API or permission handoff'
        if tools.errors.get('payments'):
            assert 'permissions' in tools.errors['payments'], 'Unexpected payments read failure'
        report = owner.remote_api.transport.summary()
        for family in ('profile','clients','invoices'):
            assert report['successful_gets'].get(family), 'Missing live read: ' + family
        for family in ('estimates','payments'):
            assert report['successful_gets'].get(family) or any(
                issue['family']==family and issue['status']==403 for issue in report['errors']), 'Missing live attempt: '+family
        assert not report['blocked_writes'], 'Unexpected write during connected read test'
    scenario = iter(connected() if live else standalone())
    state = dict(seen=0, idle=0, watchdog=started)
    def tick():
        try:
            now = time.monotonic()
            if now-started>150:
                raise RuntimeError('Billing QA timed out.')
            if now-state['watchdog']>5:
                faulthandler.dump_traceback_later(25,file=log)
                state['watchdog']=now
            if owner.state['busy'] or bill.busy or owner.resizeAnimating or owner.settingsFitPending or now<state['idle']:
                return
            if errors:
                raise RuntimeError('QML reported an error.')
            stage = next(scenario, None)
            if stage is None:
                finish()
                return
            state['seen']+=1
            log.write(stage+'\n')
            state['idle']=time.monotonic()+.85
        except Exception as exc:
            finish(exc)
    timer.timeout.connect(tick)
    timer.start()
    app._billing_qa = (timer, log, message)

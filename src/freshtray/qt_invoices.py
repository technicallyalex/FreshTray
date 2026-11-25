"""Invoice presentation, encrypted local drafts, explicit provider writes and PDF/mail export."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import queue
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QTextDocument, QFont
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog
from .billing import (BillingStore, blank_invoice, blank_line, totals, validate, import_lines,
                      invoice_html, mailto, email_file, number, money, email_address)
from .invoice_api import InvoiceAPI, normalized
from .api import ApiError
from .history_model import entry_date


class Invoices(QObject):
    changed = Signal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner=owner;self.store=BillingStore(owner.vault);self.view='list';self.draft=None;self.base=None
        self.busy=False;self.message='';self.problem='';self.filter='';self.status_filter='All';self.client_filter=''
        self.options={};self.times=[];self.expenses=[];self.imported=[];self.preview='';self.last_pdf=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='FreshTrayInvoices');self.results=queue.Queue()
        self.poll=QTimer(self);self.poll.timeout.connect(self.receive);self.poll.start(40)
        self.checkpoint=QTimer(self);self.checkpoint.setSingleShot(True);self.checkpoint.setInterval(350);self.checkpoint.timeout.connect(self.persist_draft)
        self.key=None;self.brand_attempts=set()
        from .qt_billing_tools import BillingTools
        self._tools = BillingTools(self)

    @Property(QObject, constant=True)
    def billingTools(self):
        return self._tools

    @property
    def local(self):return self.owner.local_mode or self.owner.demo

    def namespace(self):
        if self.local:return 'local'
        return 'fb:'+str(self.owner.profile.get('id',''))+':'+str((self.owner.business or {}).get('account_id',''))

    def activate(self):
        key=self.namespace()
        if key!=self.key:
            self.persist_draft();self.key=key
            saved=self.owner.vault.get('invoice_drafts',{}).get(key)
            self.draft=deepcopy(saved);self.base=deepcopy(saved);self.view='edit' if saved else 'list'
            self.message='';self.problem='';self.last_pdf=None;self.times=[];self.expenses=[]
        self.emit()
        if not self.local and not self.busy and self.owner._s.get('panel')=='invoices' and key not in self.brand_attempts:
            self.brand_attempts.add(key);self.download()

    def emit(self):self.changed.emit()

    def catalogs(self):
        data=self.store._snapshot()
        if self.local:return deepcopy(dict(clients=[c for c in data['clients'] if not c.get('archived')],
                                           projects=data['projects'],items=data['items'],services=[]))
        return deepcopy(dict(clients=[],projects=[],items=[],services=[]) | data['caches'].get(self.namespace(),{}))

    def seller_details(self):
        data=self.store._snapshot()
        if self.local:return deepcopy(data['seller'])
        return dict(name=(self.owner.business or {}).get('name',''),email='',address='',currency='USD',logo='') | deepcopy(data['caches'].get(self.namespace(),{}).get('seller',{}))

    def store_seller(self,values):
        if self.local:self.store.mutate(lambda d:d.__setitem__('seller',values))
        else:
            catalog=deepcopy(self.catalogs());catalog['seller']=values;self.store.cache(self.namespace(),catalog)

    @Property('QVariantMap',notify=changed)
    def state(self):
        data=self.store._snapshot()
        catalog = (dict(clients=data['clients'],projects=data['projects'],items=data['items'],services=[]) if self.local
                   else dict(clients=[],projects=[],items=[],services=[]) | data['caches'].get(self.namespace(),{}))
        rows=[];all_rows=[]
        book=data['books'].get(self.namespace(),[])
        seller=data['seller'] if self.local else dict(name=(self.owner.business or {}).get('name',''),email='',address='',currency='USD',logo='') | catalog.get('seller',{})
        names={str(c['id']):c['name'] for c in catalog['clients']}
        for item in book:
            if item.get('deleted'):continue
            name=names.get(item['client'],(item.get('client_snapshot') or {}).get('name','Existing client'))
            try:t=totals(item)
            except (ValueError,KeyError):continue
            status=item['status']
            if status.lower() not in ('draft','paid','autopaid','void','voided') and t['balance']!='0.00' and item['due']<date.today().isoformat():status='Overdue'
            row=dict(id=item['id'],number=item['number'] or 'Unnumbered draft',client=name,date=item['date'],due=item['due'],status=status,sync=item['sync'],total=t['total'],balance=t['balance'],currency=item['currency'],issue=item.get('issue',''),description=' '.join(' / '.join(x.get('description') or x.get('name','') for x in item['lines']).split())[:400],updated=item.get('updated') or item['date'])
            all_rows.append(row)
            if self.filter.lower() not in (item['number']+' '+name+' '+row['description']).lower():continue
            if self.status_filter!='All' and status.lower()!=self.status_filter.lower():continue
            if self.client_filter and item['client']!=self.client_filter:continue
            rows.append(row)
        summaries=[]
        for currency in sorted({r['currency'] for r in all_rows}):
            group=[r for r in all_rows if r['currency']==currency]
            summaries.append(dict(currency=currency,overdue=money(sum(number(r['balance']) for r in group if r['status']=='Overdue')),outstanding=money(sum(number(r['balance']) for r in group if r['status'].lower() not in ('draft','void','voided'))),draft=money(sum(number(r['total']) for r in group if r['status'].lower()=='draft'))))
        draft=deepcopy(self.draft) if self.draft else blank_invoice()
        try:t=totals(draft)
        except (ValueError,KeyError):t=dict(subtotal='—',discount='—',tax='—',total='—',paid='—',balance='—',amounts=[])
        for i,line in enumerate(draft['lines']):
            line['amount']=t['amounts'][i] if i<len(t['amounts']) else '—'
            line.pop('raw',None)
        if draft.get('remote'):draft['remote']={'id':draft['remote']['id']}
        projects=[]
        project_names=dict([('', 'No project')]+[(str(p['id']),p.get('name') or p.get('title','Project')) for p in catalog['projects'] if str(p.get('client_id'))==draft['client']])
        for source in self.times+self.expenses:
            if str(source.get('client_id'))==draft['client']:project_names.setdefault(str(source.get('project_id') or ''),source.get('project') or 'Other project')
        for pid,name in project_names.items():
            duration=sum(int(x['duration']) for x in self.times if str(x.get('project_id') or '')==pid and self._within(x))
            projects.append(dict(id=pid,name=name,hours=f'{duration//3600}:{duration%3600//60:02}',selected=pid in self.options.get('projects',[])))
        return deepcopy(dict(local=self.local,busy=self.busy,view=self.view,message=self.message,problem=self.problem,draft=draft,
                clients=sorted((c for c in catalog['clients'] if not c.get('archived') or str(c['id'])==draft['client']),key=lambda x:x['name'].casefold()),items=sorted(catalog['items'],key=lambda x:x['name'].casefold()),
                summaries=summaries,recent=sorted(all_rows,key=lambda r:str(r['updated']),reverse=True)[:4],rows=sorted(rows,key=lambda x:(x['date'],x['number']),reverse=True),seller=seller,totals=t,
                invoiceSeller=draft.get('seller_snapshot') or seller,projects=projects,options=self.options,importLines=self.imported,preview=self.preview,
                pending=any(x['sync'] in ('queued','sending','review','conflict') for x in book),
                records={k:data[k] for k in ('clients','projects','items','expenses')},
                editable=not self.busy and draft.get('sync') not in ('sending','review','conflict') and draft.get('status','').lower() not in ('paid','autopaid','partial','partially paid')))

    def persist_draft(self):
        if self.key is None or self.draft is None:return True
        try:
            with self.owner.vault.lock:
                previous=self.owner.vault.get('invoice_drafts',{})
                drafts=deepcopy(previous)
                stored=next((x for x in self.store._snapshot()['books'].get(self.key,[]) if x['id']==self.draft['id']),None)
                if self.draft!=stored:drafts[self.key]=deepcopy(self.draft)
                else:drafts.pop(self.key,None)
                if drafts!=previous:self.owner.vault.update(invoice_drafts=drafts)
            return True
        except OSError:self.problem='The invoice draft could not be saved. Keep the window open and retry.';self.emit();return False

    def edit_allowed(self):
        if self.busy:return False
        if self.draft and (self.draft.get('sync') in ('sending','review','conflict') or self.draft.get('status','').lower() in ('paid','autopaid','partial','partially paid')):
            raise ValueError('This invoice is read-only. Review its sync or payment status first.')
        return True

    def edited(self):
        self.last_pdf=None
        if self.draft and self.draft.get('sync')=='synced':self.draft['sync']='edited'

    def fail(self, exc):
        self.problem=str(exc) if isinstance(exc,(ValueError,ApiError)) else 'The operation could not finish. Your local data is retained.'
        self.emit()

    def job(self, work, done):
        if self.busy:return
        self.busy=True;self.problem='';self.emit()
        future=self.pool.submit(work);future.add_done_callback(lambda f:self.results.put((f,done)))

    def receive(self):
        try:f,done=self.results.get_nowait()
        except queue.Empty:return
        self.busy=False
        try:done(f.result())
        except Exception as exc:self.fail(exc)
        self.emit()

    @Slot()
    def newInvoice(self):
        if self.busy:return
        if not self.persist_draft():return
        def start():
            clients=self.catalogs()['clients'];self.draft=blank_invoice(str(clients[0]['id']) if clients else '',self.seller_details().get('currency') or 'USD')
            self.base=deepcopy(self.draft);self.view='edit';self.problem='';self.preview='';self.last_pdf=None;self.emit();self.checkpoint.start()
        if self.owner.vault.get('invoice_drafts',{}).get(self.namespace()):
            self.owner.confirm('Discard the unfinished invoice draft and start a new one?',start)
        else:start()

    @Slot(str)
    def openInvoice(self, key):
        if self.busy:return
        if not self.persist_draft():return
        saved=self.owner.vault.get('invoice_drafts',{}).get(self.namespace())
        def open_record():
            self.draft=deepcopy(saved if saved and saved['id']==key else next(x for x in self.store.rows(self.namespace()) if x['id']==key));self.base=deepcopy(self.draft)
            self.view='edit';self.last_pdf=None;self.problem='';self.emit();self.checkpoint.start()
        if saved and saved['id']!=key:self.owner.confirm('Discard the unfinished invoice draft and open this invoice?',open_record)
        else:open_record()

    @Slot()
    def back(self):
        if self.busy:return
        self.persist_draft();self.view='list';self.draft=None;self.emit()

    @Slot()
    def resume(self):
        saved=self.owner.vault.get('invoice_drafts',{}).get(self.namespace())
        if saved:self.draft=deepcopy(saved);self.base=deepcopy(saved);self.view='edit';self.emit()

    @Slot(str,str)
    def filterRows(self, query, status):self.filter=query;self.status_filter=status;self.emit()

    @Slot(str)
    def filterClient(self, client):self.client_filter=client;self.emit()

    @Slot(str,'QVariant')
    def field(self,key,value):
        try:
            if not self.edit_allowed() or not self.draft:return
            if key not in ('client','number','date','due','currency','discount','po','note','terms'):return
            if key=='client' and value!=self.draft['client'] and any(l.get('sources') for l in self.draft['lines']):
                raise ValueError('Remove imported lines before changing the invoice client.')
            if key=='client' and str(value)!=self.draft['client']:self.draft.pop('client_snapshot',None)
            self.draft[key]=str(value);self.problem='';self.edited();self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot(int,str,str)
    def line(self,index,key,value):
        try:
            if not self.edit_allowed() or not self.draft:return
            if key not in ('name','description','qty','rate','tax','taxName','tax2','taxName2'):return
            self.draft['lines'][index][key]=value;self.edited();self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot()
    def addLine(self):
        try:
            if self.edit_allowed() and self.draft and len(self.draft['lines'])<400:self.draft['lines'].append(blank_line());self.edited();self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot(int)
    def removeLine(self,index):
        try:
            if self.edit_allowed() and len(self.draft['lines'])>1:del self.draft['lines'][index];self.edited();self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot(str)
    def pickItem(self, key):
        try:
            if not self.edit_allowed():return
            item=next(x for x in self.catalogs()['items'] if str(x['id'])==key)
            if item.get('currency') and item['currency']!=self.draft['currency']:raise ValueError('The saved item uses a different currency. Add a manual line with an appropriate rate instead.')
            line=blank_line();line.update(name=item['name'],description=item.get('description',''),rate=item['rate'])
            if len(self.draft['lines'])==1 and not self.draft['lines'][0]['name']:self.draft['lines']=[]
            self.draft['lines'].append(line);self.edited();self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot()
    def save(self):
        try:
            if not self.edit_allowed() or not self.draft:return
            inv=deepcopy(self.draft);inv['sync']='local' if self.local else 'queued'
            if not inv.get('seller_snapshot'):inv['seller_snapshot']=deepcopy(self.seller_details())
            self.draft=self.store.put(self.namespace(),inv);self.base=deepcopy(self.draft)
            self.message='Saved locally.' if self.local else 'Saved locally. Use Sync drafts when you are ready to create or update the FreshBooks invoice.'
            self.problem='';self.persist_draft();self.emit()
            if self.local:self.invalidate_time_view()
        except Exception as exc:self.fail(exc)

    def invalidate_time_view(self):
        self.owner.api.clear('month');self.owner.month_loaded=None;self.owner.month_valid=False
        self.owner._s['monthReady']=False;self.owner.emit()

    def parties(self):
        if not self.draft:raise ValueError('Choose an invoice.')
        current=next((c for c in self.catalogs()['clients'] if str(c['id'])==self.draft['client']),None)
        snapshot=self.draft.get('client_snapshot')
        client=dict(current or {},**{k:v for k,v in (snapshot or {}).items() if v}) if current or snapshot else None
        if not client:raise ValueError('Download or add the invoice client first.')
        seller=self.draft.get('seller_snapshot') or self.seller_details()
        if not seller['name'].strip():raise ValueError('Add your business name in Business & local records first.')
        return client,seller

    @Slot()
    def showPreview(self):
        try:
            validate(self.draft);client,seller=self.parties();self.preview=invoice_html(self.draft,client,seller);self.view='preview';self.emit()
        except Exception as exc:self.fail(exc)

    @Slot()
    def editPreview(self):self.view='edit';self.emit()

    def make_pdf(self,path):
        validate(self.draft);client,seller=self.parties()
        if not self.draft['number']:raise ValueError('Save the local invoice or sync its number before exporting.')
        self.render_pdf(path, invoice_html(self.draft,client,seller))
        self.last_pdf=Path(path)

    def render_pdf(self, path, html):
        printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat)
        temporary=Path(str(path)+'.part');printer.setOutputFileName(str(temporary))
        document=QTextDocument();document.setDefaultFont(QFont('IBM Plex Sans',10));document.setHtml(html)
        document.print_(printer)
        if not temporary.is_file() or temporary.stat().st_size<100:raise OSError('PDF export failed')
        os.replace(temporary,path)

    def prepare_export(self):
        validate(self.draft)
        saved=next((x for x in self.store.rows(self.namespace()) if x['id']==self.draft['id']),None)
        if saved!=self.draft:
            self.save()
            if self.problem:raise ValueError(self.problem)

    @Slot()
    def exportPdf(self):
        try:
            self.prepare_export()
            path,_=QFileDialog.getSaveFileName(None,'Export invoice PDF','Invoice.pdf','PDF (*.pdf)')
            if path:self.make_pdf(Path(path if path.lower().endswith('.pdf') else path+'.pdf'));self.message='PDF exported.';self.emit()
        except Exception as exc:self.fail(exc)

    @Slot()
    def emailDraft(self):
        try:
            validate(self.draft);client,seller=self.parties()
            if not self.last_pdf or not self.last_pdf.is_file():raise ValueError('Export a PDF first, then choose Email draft. Attach that PDF in your mail app before sending.')
            if not QDesktopServices.openUrl(QUrl(mailto(self.draft,client,seller))):raise ValueError('No default email app was available. Configure one in Windows or save an email file instead.')
            self.message='Email draft opened. Attach the exported PDF and choose your sending account; nothing has been sent.';self.emit()
        except Exception as exc:self.fail(exc)

    @Slot()
    def exportEmail(self):
        try:
            self.prepare_export()
            client,seller=self.parties();email_address(client.get('email',''))
            path,_=QFileDialog.getSaveFileName(None,'Save email draft with PDF','Invoice.eml','Email (*.eml)')
            if not path:return
            with TemporaryDirectory(prefix='FreshTrayInvoice-') as folder:
                pdf=Path(folder)/'invoice.pdf';self.make_pdf(pdf)
                data=email_file(self.draft,client,seller,pdf.read_bytes())
                from .storage import atomic_write
                atomic_write(Path(path if path.lower().endswith('.eml') else path+'.eml'),data)
            self.last_pdf=None;self.message='Email file saved with the PDF attached. Open it in a compatible mail app and review before sending.';self.emit()
        except Exception as exc:self.fail(exc)

    @Slot('QVariantMap')
    def seller(self,values):
        try:
            data={k:str(values.get(k,'')).strip() for k in ('name','email','address','currency')}
            if not data['name']:raise ValueError('Enter your business name.')
            if '\r' in data['name'] or '\n' in data['name']:raise ValueError('Business names must fit on one line.')
            if data['email']:email_address(data['email'])
            if len(data['currency'])!=3 or not data['currency'].isalpha():raise ValueError('Enter a three-letter currency code.')
            data['logo']=self.seller_details().get('logo','')
            data['currency']=data['currency'].upper();self.store_seller(data);self.emit()
        except Exception as exc:self.fail(exc)

    def set_logo(self,path):
        logo=''
        if path:
            from .invoice_images import normalized_logo
            path=Path(path)
            if path.stat().st_size>10*1024*1024:raise ValueError('Choose a logo smaller than 10 MB.')
            logo=normalized_logo(path.read_bytes())
        self.store_seller(dict(self.seller_details(),logo=logo))
        if self.draft and self.edit_allowed():
            if self.draft.get('seller_snapshot'):self.draft['seller_snapshot']['logo']=logo
            self.edited();self.checkpoint.start()
            if self.view=='preview':
                client,seller=self.parties();self.preview=invoice_html(self.draft,client,seller)
        self.last_pdf=None;self.problem='';self.message='Business logo saved.' if logo else 'Business logo removed.';self.emit()

    @Slot()
    def chooseLogo(self):
        try:
            path,_=QFileDialog.getOpenFileName(None,'Choose business logo','','Images (*.png *.jpg *.jpeg)')
            if path:self.set_logo(path)
        except Exception as exc:self.fail(exc)

    @Slot()
    def removeLogo(self):
        try:self.set_logo(None)
        except Exception as exc:self.fail(exc)

    @Slot(str,'QVariantMap')
    def addRecord(self,kind,values):
        try:
            if not self.local:raise ValueError('Local records are separate. Switch to standalone mode to add them.')
            self.store.add(kind,dict(values));self.problem='';self.message='Local record saved.';self.emit()
            if kind in ('clients','projects'):
                b=self.owner;b.api.clear()
                if not b.business:b.load_profile()
                else:
                    b.clients,b.projects,b.services,_=b.api.catalog(b.business)
                    for scope in b.forms:
                        if not b.dirty(scope) and not (scope=='timer' and b.work_timer.status!='idle'):b.reset_form(scope,b.selected if scope=='month' else None)
                    b.sync_choices();b.emit()
        except Exception as exc:self.fail(exc)

    @Slot(str,str)
    def localAction(self,action,value):
        try:
            if not self.local or not self.draft or self.busy:return
            self.prepare_export()
            if action=='sent':self.draft['status']='Sent'
            elif action=='payment':
                amount=number(value,places=2)
                if amount<=0 or amount>number(totals(self.draft)['balance']):raise ValueError('Enter a payment greater than zero and no more than the balance.')
                self.draft['paid']=money(number(self.draft.get('paid',0))+amount)
                self.draft.setdefault('payments',[]).append(dict(date=date.today().isoformat(),amount=money(amount)))
                self.draft['status']='Paid' if totals(self.draft)['balance']=='0.00' else 'Partial'
            elif action=='archive':self.draft['deleted']=True
            self.store.patch(self.namespace(),self.draft['id'],**{k:v for k,v in self.draft.items() if k!='id'})
            self.last_pdf=None;self.problem='';self.message='Local invoice updated. No payment was collected and nothing was sent.'
            if action=='archive':self.draft=None;self.view='list'
            self.persist_draft();self.invalidate_time_view();self.emit()
        except Exception as exc:self.fail(exc)

    def remote_api(self):
        if self.local or not self.owner.business or not self.owner.remote_api.connected:raise ValueError('Connect FreshBooks and select a business first.')
        return InvoiceAPI(self.owner.remote_api,self.owner.business)

    @Slot()
    def download(self):
        try:
            api=self.remote_api();key=self.namespace();previous_seller=deepcopy(self.seller_details())
            def work():
                catalog=api.catalog();rows=api.invoices();seller,warnings=api.branding(rows)
                catalog['seller']={**previous_seller,**{k:v for k,v in seller.items() if v}};catalog['branding_warnings']=warnings
                downloaded=[normalized(raw) for raw in rows]
                def commit(data):
                    data['caches'][key]=dict(data['caches'].get(key,{}),**catalog)
                    book=data['books'].setdefault(key,[])
                    remote_index={(x.get('remote') or {}).get('id'):i for i,x in enumerate(book) if x.get('remote')}
                    for inv in downloaded:
                        index=remote_index.get(inv['remote']['id']);existing=book[index] if index is not None else None
                        if existing and existing['sync']!='synced':continue
                        if existing:inv['id']=existing['id']
                        inv['seller_snapshot']=deepcopy((existing or {}).get('seller_snapshot') or catalog['seller'])
                        if index is None:remote_index[inv['remote']['id']]=len(book);book.append(inv)
                        else:book[index]=inv
                # One durable transaction on the worker, never hundreds of GUI-thread writes.
                self.store.mutate(commit)
                return catalog
            def done(catalog):
                self.message='Invoices, business details and account lists saved for offline use. '+ ' '.join(catalog.get('branding_warnings',[]))
            self.job(work,done)
        except Exception as exc:self.fail(exc)

    @Slot()
    def sync(self):
        try:
            api=self.remote_api();key=self.namespace();rows=[x for x in self.store.rows(key) if x['sync']=='queued']
            def work():
                count=0
                for inv in rows:
                    self.store.patch(key,inv['id'],sync='sending',issue='')
                    try:
                        raw=api.write(inv);updated=normalized(raw);updated['id']=inv['id']
                        for field in ('source_estimate','source_estimate_remote'):
                            if inv.get(field):updated[field]=inv[field]
                        self.store.patch(key,inv['id'],**{k:v for k,v in updated.items() if k!='id'});count+=1
                    except Exception as exc:
                        uncertain=not isinstance(exc,(ValueError,ApiError)) or isinstance(exc,ApiError) and exc.uncertain
                        self.store.patch(key,inv['id'],sync='review' if uncertain else 'conflict',issue='Check FreshBooks for this invoice before retrying.' if uncertain else str(exc))
                        break
                return count
            def done(count):
                self.message=f'{count} invoice(s) confirmed by FreshBooks. Any unresolved changes remain local.'
                if self.draft:
                    match=next((x for x in self.store.rows(key) if x['id']==self.draft['id']),None)
                    if match:self.draft=deepcopy(match);self.base=deepcopy(match);self.persist_draft()
            self.job(work,done)
        except Exception as exc:self.fail(exc)

    @Slot(str)
    def review(self, action):
        try:
            if not self.draft or self.busy:return
            inv=self.draft;key=self.namespace()
            if inv['sync'] not in ('review','conflict','sending'):return
            if action=='retry':
                # Never automatically retry an ambiguous create. User must first check provider.
                self.store.patch(key,inv['id'],sync='queued',issue='');inv['sync']='queued';inv['issue']='';self.message='Queued by your explicit review. Use Sync drafts to retry.'
            elif action=='keep':
                self.store.patch(key,inv['id'],sync='local',issue='');inv['sync']='local';inv['issue']='';self.message='Kept as a local invoice; it will not sync unless saved again.'
            self.persist_draft();self.emit()
        except Exception as exc:self.fail(exc)

    @Slot()
    def openImport(self):
        try:
            if not self.edit_allowed() or not self.draft or not self.draft['client']:raise ValueError('Choose a client first.')
            self.options=dict(client=self.draft['client'],currency=self.draft['currency'],projects=['']+[str(x['id']) for x in self.catalogs()['projects'] if str(x.get('client_id'))==self.draft['client']],
                              expenses='all',format='detailed',group='service',includes=['service','project','member','date','notes'],rate='')
            self.options.update({'from':'','to':'','range':'all'})
            self.view='import';self.times=[];self.expenses=[];self.imported=[]
            if self.local:self._load_local_sources();self.rebuild_import()
            else:
                cache=self.store.data()['caches'].get(self.namespace(),{}).get('sources',{}).get(self.draft['client'])
                if cache:self.times,self.expenses=deepcopy(cache);self.rebuild_import()
                self.message='Checking for unbilled entries. Cached entries are available offline.'
            self.emit()
            if not self.local:
                self.downloadSources()
        except Exception as exc:self.fail(exc)

    def _load_local_sources(self):
        data=self.store.data();names={str(p['id']):p['name'] for p in data['projects']}
        self.times=[dict(x,date=entry_date(x).isoformat(),service='Time',project=names.get(str(x.get('project_id')),'No project'),member='Me',notes=x.get('note',''),rate=x.get('rate','0')) for x in data['time']]
        self.expenses=deepcopy(data['expenses'])

    @Slot()
    def downloadSources(self):
        try:
            api=self.remote_api();key=self.namespace();cid=self.draft['client'];catalog=deepcopy(self.catalogs())
            def work():
                if self.owner.offline and not self.owner.offline.probe():
                    return None
                return api.sources(cid)
            def done(result):
                if result is None:
                    self.message = 'Offline. Showing cached unbilled entries for this client.'
                    return
                times,expenses=result;projects={str(x['id']):x for x in catalog['projects']};services={str(x['id']):x for x in catalog.get('services',[])}
                self.times=[]
                for x in times:
                    p=projects.get(str(x.get('project_id')),{});service=services.get(str(x.get('service_id')),{})
                    rate=p.get('rate') or p.get('hourly_rate') or 0
                    if isinstance(rate,dict):rate=rate.get('amount',0)
                    member=' '.join(filter(None,[self.owner.profile.get('first_name'),self.owner.profile.get('last_name')])) if str(x.get('identity_id'))==str(self.owner.profile.get('id')) else 'Team member'
                    self.times.append(dict(x,date=entry_date(x).isoformat(),service=service.get('name','Time'),project=p.get('name') or p.get('title') or ('Other project' if x.get('project_id') else 'No project'),member=member or 'Me',notes=x.get('note',''),rate=str(rate)))
                self.expenses=[dict(x,id=x.get('id',x.get('expenseid')),client_id=x.get('clientid'),project_id=x.get('projectid'),date=x['date'],name=x.get('notes') or x.get('vendor') or 'Expense',amount=money(number(x['amount']['amount'])),currency=x['amount'].get('code',''),billed=int(x.get('status',1))!=1) for x in expenses]
                def cache_sources(data):
                    cache = data['caches'].setdefault(key, {})
                    cache.setdefault('sources', {})[cid] = [self.times, self.expenses]
                self.store.mutate(cache_sources)
                self.rebuild_import()
                known={''}|{str(p['id']) for p in catalog['projects'] if str(p.get('client_id'))==cid}
                if set(self.options['projects'])==known:
                    self.options['projects']=list(known|{str(x.get('project_id') or '') for x in self.times+self.expenses if str(x.get('client_id'))==cid});self.rebuild_import()
                self.message='Unbilled entries downloaded. Review billing rates before adding.'
            self.job(work,done)
        except Exception as exc:self.fail(exc)

    def _within(self,x):return (not self.options.get('from') or x['date']>=self.options['from']) and (not self.options.get('to') or x['date']<=self.options['to'])

    def rebuild_import(self):
        used=self.store.used_sources(self.namespace(),self.draft['id'])|{s for l in self.draft['lines'] for s in l.get('sources',[])}
        self.imported=import_lines(self.times,self.expenses,self.options,used)
        for line in self.imported:line['amount']=money(number(line['qty'])*number(line['rate']))

    @Slot(str,'QVariant')
    def importField(self,key,value):
        try:
            if hasattr(value,'toVariant'):value=value.toVariant()
            if key not in ('from','to','projects','expenses','format','group','includes','rate','range'):return
            self.options[key]=value;self.rebuild_import();self.problem='';self.emit()
        except Exception as exc:self.imported=[];self.fail(exc)

    @Slot()
    def addImport(self):
        try:
            if not self.edit_allowed():return
            self.rebuild_import()
            if not self.imported:raise ValueError('No unbilled entries match this selection.')
            lines=[l for l in self.draft['lines'] if l['name'].strip() or l.get('sources')]
            if len(lines)+len(self.imported)>400:raise ValueError('Use a grouped or simple format to keep the invoice below 400 lines.')
            self.draft['lines']=lines+deepcopy(self.imported);self.edited();self.view='edit';self.message='Entries added to the draft. Save to reserve them locally; sync to link them in FreshBooks.';self.emit();self.checkpoint.start()
        except Exception as exc:self.fail(exc)

    @Slot()
    def close(self):
        if not self.persist_draft():return False
        self.poll.stop();self.checkpoint.stop();self.pool.shutdown(wait=True,cancel_futures=True)
        return True

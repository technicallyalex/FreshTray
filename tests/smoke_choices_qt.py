"""Verify remembered selections across fresh encrypted-vault/controller instances."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,time,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from freshtray.qt_app import Controller
from freshtray.demo import Demo
from freshtray.storage import Vault,Preferences

app=QApplication([])
root=Path(__file__).resolve().parents[1]
class Catalog(Demo):
    def profile(self):
        return dict(id=42,business_memberships=[dict(role='owner',business=dict(id=10,name='Zebra business',account_id='z')),
                                              dict(role='owner',business=dict(id=20,name='Alpha business',account_id='a'))])
    def catalog(self,business):
        services=[dict(id=11,name='Zebra service'),dict(id=12,name='Alpha service')]
        return ([dict(id=1,organization='Zebra client'),dict(id=2,organization='Alpha client')],
                [dict(id=11,client_id=1,title='Zebra project',services=services),
                 dict(id=12,client_id=1,title='Alpha project',services=services)],services,[])

def settle(controller):
    deadline=time.monotonic()+5
    while controller.state['busy'] and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert not controller.state['busy']

def close(controller):
    controller.timer.stop();controller.reminder_timer.stop();controller.executor.shutdown(wait=True)

with tempfile.TemporaryDirectory() as directory:
    folder=Path(directory)
    def create():
        prefs=Preferences(folder/'settings.json');prefs.save(reminders=False)
        b=Controller(Catalog(),Vault(folder/'vault.dpapi'),prefs,root/'src/assets',root/'src/main.pyw',True,tray=False)
        b.error.connect(lambda message:(_ for _ in ()).throw(AssertionError(message)))
        b.start();settle(b);return b
    b=create()
    assert b.state['businesses']==['Alpha business','Zebra business']
    assert b.business['id']==20 and b.forms['log']['client']=='2'
    assert [item['name'] for item in b.state['clients']]==['Alpha client','Zebra client']
    b.setField('log','client','1')
    assert [p['name'] for p in b.state['log']['projects']]==['No project','Alpha project','Zebra project']
    b.setField('log','project','11');b.setField('log','service','11')
    assert [p['name'] for p in b.state['log']['services']]==['No service','Alpha service','Zebra service']
    draft=dict(b.forms['log'])
    b.applySetting('dropdown_sort','recent')
    assert Preferences(folder/'settings.json').data['dropdown_sort']=='recent'
    b.applySetting('clock','6:45');b.applySetting('period','AM')
    assert Preferences(folder/'settings.json').data['time']=='06:45'
    assert b.forms['log']==draft
    assert [p['name'] for p in b.state['clients']]==['Zebra client','Alpha client']
    assert b.state['log']['projects'][1]['value']=='11'
    assert b.state['log']['services'][1]['value']=='11'
    with patch('freshtray.qt_app.QDesktopServices.openUrl',return_value=True) as opened:
        b.openRepository();assert opened.call_args.args[0].toString()=='https://github.com/technicallyalex/FreshTray'
    b.selectBusiness(next(i for i,item in enumerate(b.businesses) if item['id']==10));b.answer(True);settle(b)
    b.setField('month','client','2')
    close(b)
    b=create()
    assert b.business['id']==10 and b.forms['log']['client']=='2' and b.forms['month']['client']=='2'
    assert b.state['businesses'][0]=='Zebra business'
    b.selectBusiness(next(i for i,item in enumerate(b.businesses) if item['id']==20));settle(b)
    assert b.forms['log']['client']=='1' and b.forms['month']['client']=='1'
    assert b.state['businesses'][b.state['businessIndex']]=='Alpha business'
    close(b)
    assert 'ui_choices' not in (folder/'settings.json').read_text()
    assert b'Zebra' not in (folder/'vault.dpapi').read_bytes()
print('PASS: alphabetical/recent dropdowns, stable IDs, per-business restart persistence, encrypted history and repository URL.')

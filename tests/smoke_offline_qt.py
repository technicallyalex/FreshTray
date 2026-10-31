"""Real offline adapter + Qt forms against fake HTTP; no account or network used."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import time
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QObject, QCoreApplication, QEvent, qInstallMessageHandler, QMetaObject, Qt, QPointF
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuick import QQuickItem
from PySide6.QtGui import QFontDatabase
from freshtray.api import FreshBooks
from freshtray.storage import Vault, Preferences
from freshtray.qt_app import Controller
from test_offline import Server
from test_core import CREDS, pair

root = Path(__file__).resolve().parents[1]
app = QApplication([]); QQuickStyle.setStyle('Basic')
for font in (root/'src/assets/fonts').glob('*.ttf'): QFontDatabase.addApplicationFont(str(font))
messages = []; qInstallMessageHandler(lambda kind, context, text: messages.append(text))
def settle(b):
    deadline = time.monotonic()+8
    while b.state['busy'] or b.syncing:
        app.processEvents(); time.sleep(.01)
        assert time.monotonic()<deadline, 'UI did not settle'
    for _ in range(5): app.processEvents(); time.sleep(.01)

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    vault = Vault(folder/'vault.dpapi'); vault.update(tokens=pair(), credentials=CREDS)
    prefs = Preferences(folder/'settings.json'); prefs.save(reminders=False)
    provider = FreshBooks(vault, Server())
    b = Controller(provider, vault, prefs, root/'src/assets', root/'src/main.pyw', False, tray=False)
    b.offline.probe = lambda: True
    b.sync_timer.stop()  # Controlled connectivity transitions, not wall-clock timing.
    errors = []; b.error.connect(errors.append)
    e = QQmlApplicationEngine(); e.rootContext().setContextProperty('backend', b)
    e.load(QUrl.fromLocalFile(str(root/'src/freshtray/qml/Main.qml')))
    assert e.rootObjects(), messages
    w = e.rootObjects()[0]; b.window = w; w.show(); b.start(); settle(b)
    assert b.state['catalogReady'], errors
    b.showSync(); settle(b)
    until=time.monotonic()+1
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    assert w.width()==min(720,b.windowBounds()['width']-16), 'Height refits must not interrupt the width transition'
    connection_height=w.height()
    assert w.findChild(QQuickItem,'appTitleBar').height()==43
    assert w.findChild(QQuickItem,'mainTabStrip').height()==46
    b.connectionSection(False)
    until=time.monotonic()+.5
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    assert w.height()>connection_height, 'Preferences should restore their full height'
    assert w.findChild(QQuickItem,'appTitleBar').height()==43
    assert w.findChild(QQuickItem,'mainTabStrip').height()==46
    b.connectionSection(True)
    until=time.monotonic()+.5
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    assert w.height()==connection_height, 'Connection height should be stable across tab changes'
    b._s['authStarted']=True; b.emit()
    until=time.monotonic()+.5
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    assert w.height()>=w.minimumHeight()
    b._s['authStarted']=False; b.emit()
    until=time.monotonic()+.5
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    client=w.findChild(QQuickItem,'oauthClient'); secret=w.findChild(QQuickItem,'oauthSecret')
    redirect=w.findChild(QQuickItem,'oauthRedirect'); sign_in=w.findChild(QQuickItem,'oauthSignIn')
    refresh=w.findChild(QQuickItem,'refreshAccountData'); disconnect=w.findChild(QQuickItem,'disconnectAccount')
    def left(item): return item.mapToScene(QPointF(0,0)).x()
    assert abs(client.width()-secret.width())<=1, 'Credential fields must have equal width'
    assert abs(client.mapToScene(QPointF(0,0)).y()-secret.mapToScene(QPointF(0,0)).y())<=1
    assert max(left(item) for item in (client,redirect,sign_in,refresh))-min(left(item) for item in (client,redirect,sign_in,refresh))<=1, 'Form/action left edges must align'
    assert abs(left(secret)+secret.width()-left(redirect)-redirect.width())<=1
    assert abs(left(disconnect)+disconnect.width()-left(redirect)-redirect.width())<=1
    w.grabWindow().save(str(root/'.build/connection-fields-light.png'))
    b.applySetting('theme','dark'); app.processEvents()
    w.grabWindow().save(str(root/'.build/connection-fields-dark.png'))
    b.applySetting('theme','light')

    b.selectPanel('month'); settle(b)
    b.offline.probe = lambda: False
    b.syncNow(); settle(b)
    assert b.state['sync']['online'] is False
    b.setField('month', 'client', '123'); b.setField('month', 'hours', '3:00'); b.setField('month', 'note', 'Offline UI test')
    b.submit('month'); settle(b)
    assert b.state['sync']['count']==1 and len(b.state['entries'])==1, errors
    eid = b.state['entries'][0]['id']; assert eid.startswith('local-')
    b.editEntry(eid); settle(b)
    b.setField('month', 'note', 'Edited offline'); b.submit('month'); settle(b)
    assert b.entries[0]['note']=='Edited offline' and b.state['sync']['count']==1, errors
    b.deleteEntry(eid); QMetaObject.invokeMethod(w.findChild(QObject, 'confirmDialog'), 'accept', Qt.DirectConnection); settle(b)
    assert not b.entries and b.state['sync']['count']==0, errors
    b.setField('month', 'client', '123'); b.setField('month', 'hours', '3:00'); b.submit('month'); settle(b)
    assert b.state['sync']['count']==1
    b.offline.probe = lambda: True; b.syncNow(); settle(b)
    assert b.state['sync']['count']==0 and len(b.entries)==1, errors
    assert not str(b.entries[0]['id']).startswith('local-')
    # Conflict review controls must be functional in both themes and compact settings.
    eid = str(b.entries[0]['id']); b.editEntry(eid); settle(b)
    b.setField('month', 'note', 'Local intent'); b.submit('month'); settle(b)
    provider.transport.rows[int(eid)]['note'] = 'Changed elsewhere'
    b.syncNow(); settle(b)
    assert b.state['sync']['problems'][0]['status']=='conflict', errors
    b.showSync(); settle(b)
    # Wait for the resize mask and toast to settle before reviewing the panel.
    until = time.monotonic()+.5
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    for theme in ('light', 'dark'):
        b.applySetting('theme', theme); app.processEvents()
        for _ in range(10): app.processEvents(); time.sleep(.01)
        w.grabWindow().save(str(root/'.build'/('offline-review-'+theme+'.png')))
    assert w.findChild(QObject, 'syncReviewChoice') is not None
    b.applySetting('docked_mode',True)
    from PySide6.QtQuick import QQuickWindow
    other=QQuickWindow(); other.setTitle('Offline test focus target'); other.show(); other.requestActivate()
    until=time.monotonic()+.4
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
    assert w.isVisible(), 'Changing focus must not hide the docked app'
    other.close(); other.deleteLater()
    b.applySetting('docked_mode',False)
    assert not errors, errors
    assert not [m for m in messages if 'Error' in m or 'ReferenceError' in m or 'TypeError' in m], messages
    b.timer.stop(); b.reminder_timer.stop(); b.delay_timer.stop(); b.sync_timer.stop()
    b.local_executor.shutdown(wait=True); b.executor.shutdown(wait=True)
    e.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
print('PASS: offline Qt add/edit/delete, reconnect sync, conflict review and themed panels; no live API calls.')

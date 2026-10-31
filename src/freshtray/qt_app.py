"""Qt Quick presentation adapter. API work is serialized off the GUI thread.

The vault, API validation, one-use OAuth refresh and pending-write journal are
shared with the original interface. QML receives names and form state, never tokens.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
import calendar
import queue
import sys
import time

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, Qt, QUrl, QPoint
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

from .api import ApiError, OAuthAttempt, DEFAULT_REDIRECT
from .history_model import (month_after, day_totals, entry_date, format_duration,
                            hours_input, edit_payload, edit_restriction)
from .model import entry_payload, display_reminder_time, parse_reminder_time, reminder_due, matching_entry
from .read_cache import ReadCache
from .offline import OfflineAPI
from .storage import Vault
from .alert_sound import PopupChime, SOUNDS, sound_settings
from .reminder_delay import ReminderDelay, delay_minutes
from .choice_history import ChoiceHistory
from . import __version__
from .windows import startup_enabled, set_startup


def ident(item):
    return str(item.get('id', item.get('userid', '')))


def client_name(item):
    return item.get('organization') or ' '.join(filter(None, [item.get('fname'), item.get('lname')])) or 'Unnamed client'


class Controller(QObject):
    changed = Signal()
    toast = Signal(str)
    error = Signal(str)
    reminder = Signal()
    fitRequested = Signal()
    confirmation = Signal(str, str)
    calendarChanged = Signal()
    preferencesChanged = Signal()

    def __init__(self, api, vault, prefs, assets, launcher, demo=False, tray=True):
        super().__init__()
        self.offline = None if demo else OfflineAPI(api, vault, Vault(vault.path.parent/'offline.dpapi'))
        if self.offline and hasattr(api.transport, 'timeout'):
            api.transport.timeout = 8
        self.api, self.vault, self.prefs = self.offline or ReadCache(api), vault, prefs
        self.syncing, self.next_sync, self.retry_delay = False, 0, 15
        self.assets, self.launcher, self.demo = Path(assets), launcher, demo
        self.choices = ChoiceHistory(vault)
        self.popup_chime = PopupChime(self.assets/'sounds/reminder.wav')
        self.window = None
        self.screen_geometry = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='FreshTrayAPI')
        self.local_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='FreshTrayLocal')
        self.results = queue.Queue()
        self.businesses, self.clients, self.projects, self.services = [], [], [], []
        self.profile, self.business, self.entries = {}, None, []
        self.month, self.selected = date.today().replace(day=1), date.today()
        self.month_loaded, self.month_valid = None, False
        self.forms, self.baselines, self.originals = {}, {}, {}
        for scope in ('log', 'month'):
            self.reset_form(scope)
        self.attempt = None
        self.pending_action = None
        self.last_delivered = ''
        self.reminder_is_followup = False
        self._s = dict(panel='log' if api.connected else 'settings', busy=False, loading='',
                       connected=bool(api.connected), catalogReady=False, demo=demo, version=__version__,
                       businesses=[], businessIndex=-1, clients=[], calendar=[], weeks=[],
                       entries=[], entryPage=0, dayTotal='0:00', monthTotal='0:00',
                       selected=self.selected.isoformat(), selectedLabel='', month=self.month.month,
                       year=self.month.year, years=[], monthReady=False, warning='',
                       settings=self.settings_state(), connectionSection=not api.connected,
                       clientId=(vault.get('credentials') or {}).get('client_id', ''),
                       redirect=(vault.get('credentials') or {}).get('redirect_uri', DEFAULT_REDIRECT), authStarted=False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(25)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.tick)
        self.reminder_timer.start(15000)
        self.delayed_reminder = ReminderDelay(prefs)
        self.delay_timer = QTimer(self)
        self.delay_timer.setSingleShot(True)
        self.delay_timer.timeout.connect(self.deliver_delayed_reminder)
        self.arm_delayed_reminder()
        self.tray = None
        if tray:
            self.tray = QSystemTrayIcon(QIcon(str(self.assets / 'freshtray.ico')), self)
            menu = QMenu()
            for title, callback in [('Log time', lambda: self.show_panel('log')),
                                    ('Monthly hours', lambda: self.show_panel('month')),
                                    ('Settings', lambda: self.show_panel('settings')),
                                    ('Test reminder', self.testReminder), ('Quit FreshTray', self.requestQuit)]:
                menu.addAction(title, callback)
            self.tray.setContextMenu(menu)
            self.tray.setToolTip('FreshTray — log your day')
            self.tray.activated.connect(lambda reason: self.show_panel(self._s['panel']) if reason in
                                        (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
            self.tray.messageClicked.connect(lambda: self.show_panel('log'))
            self.tray.show()
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.syncOffline)
        self.sync_timer.start(5000)
        self.rebuild_calendar()

    @Property('QVariantMap', notify=changed)
    def state(self):
        return dict(self._s, log=self.form_view('log'), monthForm=self.form_view('month'),
                    sync=self.offline.status() if self.offline else dict(online=True, count=0, problems=[], message=''), syncing=self.syncing, legacyPending=self.offline.legacy_pending() if self.offline else bool(self.vault.get('pending')))

    @Property('QVariantList', notify=calendarChanged)
    def calendar(self):
        return self._s['calendar']

    @Property(bool, constant=True)
    def reducedMotion(self):
        import ctypes
        enabled = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
        return not bool(enabled.value)

    @Slot(result='QVariantMap')
    def windowBounds(self):
        screen = self.window.screen() if self.window else QApplication.primaryScreen()
        if self.screen_geometry:
            return self.screen_geometry()
        rect = screen.availableGeometry()
        return dict(x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height())

    @Slot(int, int, result='QVariantMap')
    def reminderPlacement(self, preferred_width, preferred_height):
        saved = self.prefs.data.get('reminder_position')
        valid = isinstance(saved, dict) and all(type(saved.get(k)) is int for k in ('x', 'y'))
        if self.screen_geometry:
            area = self.screen_geometry()
        else:
            screen = None
            if valid:
                screen = QApplication.screenAt(QPoint(saved['x']+preferred_width//2, saved['y']+preferred_height//2))
            if screen is None:
                screen = self.window.screen() if self.window else QApplication.primaryScreen()
            rect = screen.availableGeometry()
            area = dict(x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height())
        width, height = min(preferred_width, area['width']-32), min(preferred_height, area['height']-32)
        left, top = area['x']+8, area['y']+8
        right, bottom = area['x']+area['width']-width-8, area['y']+area['height']-height-8
        x = saved['x'] if valid else round(area['x']+(area['width']-width)/2)
        y = saved['y'] if valid else round(area['y']+(area['height']-height)/2)
        return dict(x=max(left,min(x,right)), y=max(top,min(y,bottom)), width=width, height=height, bottom=bottom)

    @Slot(int, int)
    def rememberReminderPosition(self, x, y):
        position = dict(x=x, y=y)
        if self.prefs.data.get('reminder_position') != position:
            try:
                self.prefs.save(reminder_position=position)
            except OSError:
                self.error.emit('The reminder position could not be saved.')

    def emit(self):
        self.changed.emit()

    def settings_state(self):
        clock, period = display_reminder_time(self.prefs.data['time'])
        return dict(self.prefs.data, clock=clock, period=period,
                    popup_sound_options=[dict(value=key, name=label) for key, (label, _) in SOUNDS.items()],
                    startup=False if self.demo else startup_enabled())

    def ordered(self, items, name, kind):
        return self.choices.ordered(items, name, kind, self.profile.get('id'),
                                    '' if kind == 'business' else (self.business or {}).get('id', ''),
                                    self.prefs.data.get('dropdown_sort', 'alphabetical'))

    def sync_choices(self):
        self.businesses = self.ordered(self.businesses, lambda b: b['name'], 'business')
        self._s['businesses'] = [b['name'] for b in self.businesses]
        self._s['businessIndex'] = next((i for i,b in enumerate(self.businesses)
                                         if self.business and ident(b) == ident(self.business)), -1)
        self._s['clients'] = [dict(value=ident(c), name=client_name(c))
                              for c in self.ordered(self.clients, client_name, 'client')]

    def remember_choice(self, kind, value):
        try:
            self.choices.remember(kind, value, self.profile.get('id'),
                                  '' if kind == 'business' else (self.business or {}).get('id', ''))
        except OSError:
            self.error.emit('This selection could not be remembered. Your current entry is still available.')

    @Slot()
    def openRepository(self):
        if not QDesktopServices.openUrl(QUrl('https://github.com/technicallyalex/FreshTray')):
            self.error.emit('Your browser could not open the FreshTray repository.')

    def reset_form(self, scope, day=None):
        clients = self.ordered(self.clients, client_name, 'client')
        client = self.choices.selected(clients, 'client', self.profile.get('id'), (self.business or {}).get('id', ''))
        self.forms[scope] = dict(client=client,
                                 project='', service='', day=(day or date.today()).isoformat(),
                                 hours='8:00', note='', billable=True)
        self.originals[scope] = None
        self.baselines[scope] = deepcopy(self.forms[scope])

    def dirty(self, scope):
        return self.forms[scope] != self.baselines[scope]

    def form_view(self, scope):
        form = self.forms[scope]
        projects = [p for p in self.projects if str(p.get('client_id')) == form['client']]
        projects = self.ordered(projects, lambda p: p.get('title') or 'Untitled project', 'project')
        chosen = next((p for p in projects if ident(p) == form['project']), None)
        services = (chosen.get('services') or []) if chosen else self.services
        services = list(services)
        if form['service'] and not any(ident(s) == form['service'] for s in services):
            services.append({'id': form['service'], 'name': 'Existing service'})
        services = self.ordered(services, lambda item: item.get('name') or 'Unnamed service', 'service')
        return dict(form, projects=[dict(value='', name='No project')] +
                    [dict(value=ident(p), name=p.get('title') or 'Untitled project') for p in projects],
                    services=[dict(value='', name='No service')] +
                    [dict(value=ident(s), name=s.get('name') or 'Unnamed service') for s in services],
                    editing=bool(self.originals[scope]),
                    billed=bool((self.originals[scope] or {}).get('billed')))

    @Slot(str, str, 'QVariant')
    def setField(self, scope, key, value):
        if self._s['busy'] or scope not in self.forms or key not in self.forms[scope]:
            return
        form = self.forms[scope]
        if key in ('client', 'project', 'service'):
            value = str(value)
        if key == 'client' and value != form['client']:
            form.update(project='', service='')
        if key == 'project' and value != form['project']:
            form['service'] = ''
        form[key] = value
        if key in ('client', 'project', 'service') and value:
            self.remember_choice(key, value)
            self.sync_choices()
        self.emit()

    def run(self, kind, work, done):
        if self._s['busy']:
            return False
        self._s.update(busy=True, loading=kind)
        self.emit()
        executor = self.local_executor if self.offline and kind in ('save', 'delete', 'entry', 'month', 'catalog') else self.executor
        future = executor.submit(work)
        future.add_done_callback(lambda result: self.results.put((result, done, False)))
        return True

    def poll(self):
        try:
            future, done, background = self.results.get_nowait()
        except queue.Empty:
            return
        if background:
            self.syncing = False
        if not background:
            self._s.update(busy=False, loading='')
        try:
            done(future.result())
        except (ValueError, ApiError, OSError) as exc:
            self.error.emit(str(exc))
        except Exception:
            # Provider responses and credentials must not enter logs or dialogs.
            self.error.emit('The operation could not finish. Your draft is retained. Try again or reconnect in Settings.')
        self.emit()

    @Slot()
    def start(self):
        if self.api.connected:
            self.load_profile()

    def load_profile(self):
        def loaded(profile):
            self.profile = profile
            self.businesses = [m['business'] for m in profile.get('business_memberships', [])
                               if m.get('role') != 'client' and m.get('business', {}).get('account_id')
                               and m['business'].get('active', True)]
            self.businesses = self.ordered(self.businesses, lambda b: b['name'], 'business')
            self._s.update(connected=True, businesses=[b['name'] for b in self.businesses])
            if not self.businesses:
                raise ValueError('No eligible FreshBooks business. Check your membership and permissions.')
            preferred = next(iter(self.choices.recent('business', self.profile['id'])), str(self.prefs.data.get('business_id') or ''))
            index = next((i for i,b in enumerate(self.businesses) if ident(b) == preferred), 0)
            self.load_catalog(index)
        self.run('catalog', self.api.profile, loaded)

    def load_catalog(self, index, remember=False):
        business = self.businesses[index]
        self._s.update(catalogReady=False, monthReady=False)
        def loaded(result):
            self.business = business
            self.clients, self.projects, self.services, warnings = result
            self.prefs.save(business_id=business['id'])
            if remember:
                self.remember_choice('business', business['id'])
            self._s.update(businessIndex=index, clients=[dict(value=ident(c), name=client_name(c)) for c in self.clients],
                           catalogReady=True, warning=' '.join(warnings))
            self.sync_choices()
            self.month_loaded, self.month_valid, self.entries = None, False, []
            for scope in self.forms:
                self.reset_form(scope, self.selected if scope == 'month' else None)
            self.rebuild_calendar()
            if self._s['panel'] == 'month':
                self.load_month()
        self.run('catalog', lambda: self.api.catalog(business), loaded)

    def confirm(self, text, action, title="Please confirm"):
        self.pending_action = action
        self.confirmation.emit(title, text)

    @Slot(bool)
    def answer(self, accepted):
        action, self.pending_action = self.pending_action, None
        if accepted and action:
            action()

    @Slot(int)
    def selectBusiness(self, index):
        if self._s['busy'] or index == self._s['businessIndex'] or not 0 <= index < len(self.businesses):
            return
        if any(self.dirty(scope) or self.originals[scope] for scope in self.forms):
            self.confirm('Changing business will discard your unsaved entry drafts.', lambda: self.load_catalog(index, remember=True))
        else:
            self.load_catalog(index, remember=True)
        self.emit()

    @Slot(str)
    def selectPanel(self, panel):
        if panel not in ('log', 'month', 'settings'):
            return
        self._s['panel'] = panel
        if panel == 'month' and self.business and not self._s['busy']:
            self.load_month()
        self.emit()
        self.fitRequested.emit()

    def show_panel(self, panel):
        self.selectPanel(panel)
        if self.window:
            self.window.showNormal()
            self.window.raise_()
            self.window.requestActivate()

    def load_month(self, force=False):
        if not self.business or self._s['busy']:
            return
        key = (self.business['id'], self.month, self.profile['id'])
        if not force and self.month_loaded == key and self.month_valid:
            return  # Tab changes never fetch or rebuild an already-loaded month.
        if force:
            self.api.clear('month')
        cached = self.api.peek_month(*key)
        def loaded(entries):
            self.entries, self.month_loaded, self.month_valid = entries, key, True
            self._s['monthReady'] = True
            self.rebuild_calendar()
        self.month_valid = False
        self._s['monthReady'] = False
        if cached is not None:
            loaded(cached)
        else:
            self.run('month', lambda: self.api.entries_for_month(*key), loaded)

    def rebuild_calendar(self):
        totals = day_totals(self.entries)
        counts = {}
        for entry in self.entries:
            day = entry_date(entry)
            counts[day] = counts.get(day, 0) + 1
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.month.year, self.month.month)
        cells, summaries = [], []
        for week in weeks:
            summaries.append(format_duration(sum(totals.get(day, 0) for day in week if day.month == self.month.month)))
            for day in week:
                in_month = day.month == self.month.month
                cells.append(dict(day=day.day, iso=day.isoformat(), current=in_month,
                                  today=day == date.today(), selected=day == self.selected,
                                  hours=format_duration(totals.get(day, 0)) if in_month and counts.get(day) else '',
                                  hasEntry=bool(in_month and counts.get(day)), entryCount=counts.get(day, 0) if in_month else 0))
        rows = [dict(id=str(e['id']), client=next((client_name(c) for c in self.clients if ident(c)==str(e.get('client_id'))), 'Existing client'),
                     hours=format_duration(e.get('duration')), note=e.get('note') or '', billed=bool(e.get('billed')),
                     sync=e.get('_sync', ''), restriction=edit_restriction(e)) for e in self.entries if entry_date(e) == self.selected]
        self._s.update(calendar=cells, weeks=summaries, rows=len(weeks), entries=rows,
                       entryPage=min(self._s.get('entryPage', 0), max(0, (len(rows)-1)//self._s.get('entryPageSize', 2))),
                       month=self.month.month, year=self.month.year,
                       years=[str(y) for y in range(min(9998, self.month.year+20), max(1, self.month.year-20)-1, -1)],
                       selected=self.selected.isoformat(), selectedLabel=self.selected.strftime('%A, %B %d, %Y'),
                       dayTotal=format_duration(totals.get(self.selected, 0)),
                       monthTotal=format_duration(sum(totals.values())))
        self.calendarChanged.emit()
        self.emit()

    @Slot(int)
    def shiftMonth(self, offset):
        try:
            chosen = month_after(self.month, offset)
            self.chooseMonth(chosen.year, chosen.month)
        except ValueError:
            pass

    @Slot(int, int)
    def chooseMonth(self, year, month):
        if self._s['busy'] or not 1 <= year <= 9998 or not 1 <= month <= 12:
            return
        chosen = date(year, month, 1)
        if chosen == self.month:
            return
        def change():
            self.month, self.selected = chosen, chosen
            self.reset_form('month', chosen)
            self.entries, self.month_valid = [], False
            self.rebuild_calendar()
            self.load_month()
        if self.dirty('month') or self.originals['month']:
            self.confirm('Discard the monthly editor draft and change month?', change)
        else:
            change()

    @Slot()
    def today(self):
        if self.month == date.today().replace(day=1):
            self.selectDay(date.today().isoformat())
        else:
            def change():
                self.month, self.selected = date.today().replace(day=1), date.today()
                self.entries, self.month_valid = [], False
                self.reset_form('month', self.selected)
                self.rebuild_calendar()
                self.load_month()
            if self.dirty('month') or self.originals['month']:
                self.confirm('Discard the monthly editor draft and go to today?', change)
            else:
                change()

    @Slot(str)
    def selectDay(self, value):
        if self._s['busy']:
            return
        try:
            chosen = date.fromisoformat(value)
        except ValueError:
            return
        if chosen.month != self.month.month or chosen.year != self.month.year or chosen == self.selected:
            return
        def change():
            self.selected = chosen
            self._s['entryPage'] = 0
            self.reset_form('month', chosen)
            self.rebuild_calendar()
        if self.dirty('month') or self.originals['month']:
            self.confirm('Discard the monthly editor draft and select another day?', change)
        else:
            change()

    @Slot(int)
    def setEntryPageSize(self, value):
        size = max(1, min(2, value))
        old = self._s.get('entryPageSize', 2)
        if size != old:
            self._s['entryPageSize'] = size
            self.entryPage(self._s.get('entryPage', 0)*old//size)

    @Slot(int)
    def entryPage(self, value):
        self._s['entryPage'] = max(0, min(value, max(0, (len(self._s['entries'])-1)//self._s.get('entryPageSize', 2))))
        self.emit()

    @Slot(str)
    def editEntry(self, entry_id):
        if self._s['busy'] or not self.month_valid:
            return
        def fetch():
            bid = self.business['id']
            def loaded(entry):
                expected_id = self.offline.data['aliases'].get(entry_id, entry_id) if self.offline else entry_id
                if str(entry.get('id')) != expected_id or str(entry.get('identity_id')) != str(self.profile['id']):
                    raise ValueError('Only your own matching time entry can be edited.')
                restriction = edit_restriction(entry)
                if restriction:
                    raise ValueError(restriction)
                cid, pid, sid = str(entry['client_id']), str(entry.get('project_id') or ''), str(entry.get('service_id') or '')
                if not any(ident(c) == cid for c in self.clients):
                    self.clients.append(dict(id=cid, organization='Existing client'))
                    self.sync_choices()
                project = next((p for p in self.projects if ident(p) == pid), None)
                if pid and not project:
                    self.projects.append(dict(id=pid, client_id=cid, title='Existing project', services=[]))
                elif project and str(project.get('client_id')) != cid:
                    raise ValueError('This project now belongs to a different client. Review it in FreshBooks.')
                self.forms['month'] = dict(client=cid, project=pid, service=sid, day=entry_date(entry).isoformat(),
                                           hours=hours_input(entry.get('duration')), note=entry.get('note') or '',
                                           billable=bool(entry.get('billable')))
                self.originals['month'] = deepcopy(entry)
                self.baselines['month'] = deepcopy(self.forms['month'])
            self.run('entry', lambda: self.api.get_entry(bid, entry_id), loaded)
        if self.dirty('month') or self.originals['month']:
            self.confirm('Replace the monthly editor draft with this entry?', fetch)
        else:
            fetch()

    def deleted_entry(self, result):
        if not self.business or str(result.get('business_id', self.business['id'])) != str(self.business['id']):
            self.toast.emit('Time entry deletion confirmed')
            return
        entry_id = str(result['id'])
        for scope in self.forms:
            if str((self.originals[scope] or {}).get('id')) == entry_id:
                self.reset_form(scope, self.selected if scope == 'month' else None)
        self.entries = [entry for entry in self.entries if str(entry['id']) != entry_id]
        self.month_valid, self.month_loaded = False, None
        self._s['monthReady'] = False
        self.rebuild_calendar()
        self.toast.emit('Deletion saved locally · waiting to sync' if result.get('_queued') else 'Preview entry deleted' if self.demo else 'Time entry deleted')
        self.next_sync = 0
        if self._s['panel'] == 'month':
            self.load_month(force=True)

    @Slot(str)
    def deleteEntry(self, entry_id):
        if self._s['busy'] or not self.month_valid or not self.business:
            return
        original = next((deepcopy(entry) for entry in self.entries if str(entry['id']) == entry_id), None)
        if not original:
            return
        if str(original.get('identity_id')) != str(self.profile['id']):
            self.error.emit('Only your own entries can be deleted.')
            return
        restriction = edit_restriction(original)
        if restriction:
            self.error.emit(restriction)
            return
        editing = str((self.originals['month'] or {}).get('id')) == entry_id
        client = next((client_name(c) for c in self.clients if ident(c)==str(original.get('client_id'))), 'this client')
        message = f"Delete {format_duration(original.get('duration'))} hours for {client} on {entry_date(original).strftime('%B %d, %Y')}? This cannot be undone in FreshTray."
        if original.get('note'):
            message += '\n\nNote: ' + original['note'][:160]
        if original.get('billed'):
            message += ' This entry is already billed. Review the related invoice in FreshBooks after deleting it.'
        if editing and self.dirty('month'):
            message += ' Unsaved edits for this entry will also be discarded.'
        bid, identity = self.business['id'], self.profile['id']
        def remove():
            self.run('delete', lambda: self.api.delete_entry(bid, entry_id, original, identity), self.deleted_entry)
        self.confirm(message, remove, "Delete time entry")

    @Slot(str)
    def clearForm(self, scope):
        if self._s['busy'] or scope not in self.forms:
            return
        def clear():
            self.reset_form(scope, self.selected if scope == 'month' else None)
            self.emit()
        if self.dirty(scope):
            self.confirm('Discard this unsaved entry?', clear)
        else:
            clear()

    @Slot(str)
    def submit(self, scope):
        if self._s['busy'] or not self.business or not self._s['catalogReady'] or scope not in self.forms:
            return
        if scope == 'month' and not self.month_valid:
            self.error.emit('Load this month successfully before saving an entry.')
            return
        try:
            form, original = deepcopy(self.forms[scope]), deepcopy(self.originals[scope])
            if not form['client']:
                raise ValueError('Choose a client before saving.')
            args = (form['client'], form['day'], form['hours'], form['note'], form['billable'], self.profile['id'], form['project'], form['service'])
            payload = edit_payload(original, *args) if original else entry_payload(*args)
            bid = self.business['id']
        except ValueError as exc:
            self.error.emit(str(exc))
            return
        def save():
            def saved(entry):
                self.remember_choice('business', bid)
                for kind in ('client', 'project', 'service'):
                    self.remember_choice(kind, form[kind])
                self.sync_choices()
                self.reset_form(scope, entry_date(entry))
                self.month_valid, self.month_loaded = False, None
                self._s['monthReady'] = False
                if scope == 'month':
                    self.selected = entry_date(entry)
                    self.month = self.selected.replace(day=1)
                    self.entries = []
                    self.rebuild_calendar()
                self.next_sync = 0
                self.toast.emit(('Saved locally · waiting to sync' if entry.get('_sync') else 'Preview saved locally' if self.demo else 'Changes saved' if original else 'Time logged') +
                                ' · ' + format_duration(payload['time_entry']['duration']) + ' hours')
                if self._s['panel'] == 'month':
                    self.load_month()
            work = (lambda: self.api.update_entry(bid, original['id'], payload, original)) if original else lambda: self.api.submit(bid, payload)
            self.run('save', work, saved)
        previous = self.vault.get('last_success')
        queued_duplicate = self.offline and any(o['kind'] == 'create' and str(o['business']) == str(bid) and o['payload'] == payload for o in self.offline.data['outbox'])
        if not original and queued_duplicate:
            self.confirm('This exact entry is already waiting to sync. Add another copy?', save)
        elif not original and previous and previous['business_id'] == bid and previous['payload'] == payload:
            self.confirm('This exact entry was already saved. Add another copy?', save)
        else:
            save()

    @Slot(str, 'QVariant')
    def applySetting(self, key, value):
        allowed = ('clock', 'period', 'reminders', 'reminder_popup', 'weekdays_only',
                   'startup', 'always_on_top', 'docked_mode', 'close_to_tray', 'theme', 'dropdown_sort', 'remind_me_minutes', 'popup_sound', 'popup_sound_choice', 'remind_me_sound_choice', 'popup_volume')
        if key not in allowed:
            return
        values = self.settings_state()
        values[key] = value
        self.saveSettings(values, notify=False)

    @Slot('QVariantMap')
    def saveSettings(self, values, notify=True):
        try:
            values = dict(values)
            stored = parse_reminder_time(values.pop('clock'), values.pop('period'))
            startup = values.pop('startup')
            allowed = ('reminders', 'reminder_popup', 'weekdays_only', 'always_on_top', 'docked_mode', 'close_to_tray', 'theme', 'dropdown_sort', 'remind_me_minutes', 'popup_sound', 'popup_sound_choice', 'remind_me_sound_choice', 'popup_volume')
            clean = {k: values[k] for k in allowed if k in values}
            if 'popup_sound_choice' in clean or 'popup_volume' in clean:
                clean['popup_sound_choice'], clean['popup_volume'] = sound_settings(clean.get('popup_sound_choice', 'ethereal'), clean.get('popup_volume', 60))
            if 'remind_me_sound_choice' in clean:
                clean['remind_me_sound_choice'], _ = sound_settings(clean['remind_me_sound_choice'], clean.get('popup_volume',60))
            if 'remind_me_minutes' in clean:
                clean['remind_me_minutes'] = delay_minutes(clean['remind_me_minutes'])
            if clean.get('dropdown_sort', 'alphabetical') not in ('alphabetical', 'recent'):
                raise ValueError('Choose Alphabetical or Recently used for dropdown sorting.')
            if not self.demo and bool(startup) != startup_enabled():
                set_startup(bool(startup), self.launcher)
            previous = dict(self.prefs.data)
            self.prefs.save(time=stored, **clean)
            if (previous.get('popup_sound',True) and not self.prefs.data.get('popup_sound',True)) or any(previous.get(k) != self.prefs.data.get(k) for k in ('popup_sound_choice', 'remind_me_sound_choice', 'popup_volume')):
                self.popup_chime.stop()
            self._s['settings'] = self.settings_state()
            self.sync_choices()
            self.preferencesChanged.emit()
            self.emit()
            if any(previous.get(key) != self.prefs.data.get(key) for key in ('always_on_top', 'docked_mode')):
                self.apply_window_flags()
            if any(previous.get(key) != self.prefs.data.get(key) for key in ('theme', 'docked_mode')):
                self.fitRequested.emit()
            if notify:
                self.toast.emit('Settings saved')
        except (ValueError, OSError) as exc:
            self._s['settings'] = self.settings_state()
            self.preferencesChanged.emit()
            self.emit()
            self.error.emit(str(exc))

    @Slot(bool)
    def connectionSection(self, value):
        self._s['connectionSection'] = value
        self.emit()
        self.fitRequested.emit()

    @Slot(str, str, str)
    def beginConnect(self, client_id, secret, redirect):
        if self.demo:
            self.error.emit('Offline preview does not connect to FreshBooks.')
            return
        if self._s['busy']:
            return
        try:
            credentials = dict(client_id=client_id.strip(), client_secret=secret or
                               (self.vault.get('credentials') or {}).get('client_secret', ''), redirect_uri=redirect.strip())
            self.attempt = OAuthAttempt(credentials)
            if not QDesktopServices.openUrl(QUrl(self.attempt.url())):
                raise ValueError('Your browser could not open. Check your default browser and try again.')
            self._s['authStarted'] = True
            self.emit()
            self.toast.emit('Sign in, then paste the complete return URL below')
        except ValueError as exc:
            self.error.emit(str(exc))

    @Slot()
    def cancelConnect(self):
        if not self._s['busy']:
            self.attempt = None
            self._s['authStarted'] = False
            self.emit()

    @Slot(str)
    def finishConnect(self, returned):
        if not self.attempt or self._s['busy']:
            self.error.emit('Start a new browser sign-in first.')
            return
        def connect():
            def done(_):
                self.attempt = None
                self._s['authStarted'] = False
                self._s.update(connected=True, clientId=(self.vault.get('credentials') or {}).get('client_id', ''))
                self.toast.emit('Connected to FreshBooks')
                self.load_profile()
            self.run('connect', lambda: self.api.connect(self.attempt, returned), done)
        if any(self.dirty(s) or self.originals[s] for s in self.forms):
            self.confirm('Reconnecting will discard unsaved entry drafts after sign-in succeeds.', connect)
        else:
            connect()

    @Slot()
    def disconnect(self):
        if self._s['busy']:
            return
        def revoke():
            def done(_):
                self.profile, self.business, self.entries = {}, None, []
                self.clients, self.projects, self.services = [], [], []
                self.month_valid, self.month_loaded = False, None
                self._s.update(connected=False, catalogReady=False, monthReady=False, businesses=[], clients=[], businessIndex=-1)
                for scope in self.forms:
                    self.reset_form(scope)
                self.rebuild_calendar()
                self.toast.emit('Disconnected')
            self.run('connect', self.api.disconnect, done)
        self.confirm('Disconnect FreshTray from FreshBooks? Saved credentials and downloaded account data will be removed from this PC after disconnection succeeds. Entries already saved in FreshBooks stay unchanged. Unsaved drafts will be discarded.', revoke)

    @Slot()
    def reloadCatalog(self):
        if self._s['busy']:
            return
        def reload():
            self.api.clear()
            self.next_sync = 0
            self.load_profile()
        if any(self.dirty(s) or self.originals[s] for s in self.forms):
            self.confirm('Reload account lists and discard unsaved entry drafts?', reload)
        else:
            reload()

    @Slot()
    def syncOffline(self):
        if not self.offline or self.syncing or self._s['busy'] or not self.api.connected or time.monotonic() < self.next_sync:
            return
        self.syncing = True
        def done(count):
            self.syncing = False
            status = self.offline.status()
            self.retry_delay = min(60, self.retry_delay*2) if status['online'] is False else 15
            self.next_sync = time.monotonic() + self.retry_delay
            if self.business:
                catalog = deepcopy(self.offline.data['catalogs'].get(str(self.business['id'])))
                if catalog:
                    self.clients, self.projects, self.services, warnings = catalog
                    # Keep draft selections visible even if archived remotely.
                    for form in self.forms.values():
                        if form['client'] and not any(ident(c) == form['client'] for c in self.clients):
                            self.clients.append(dict(id=form['client'], organization='Existing client'))
                        if form['project'] and not any(ident(p) == form['project'] for p in self.projects):
                            self.projects.append(dict(id=form['project'], client_id=form['client'], title='Existing project', services=[]))
                    self.sync_choices()
            # Replace calendar data without touching an open editor or its draft.
            if self.business and self.month_loaded:
                self.entries = self.offline.view_month(self.business['id'], self.month, self.profile['id'])
                self.rebuild_calendar()
            if count:
                self.toast.emit(f'{count} change' + ('s' if count != 1 else '') + ' synced to FreshBooks')
            self.emit()
        def work():
            try:
                return self.offline.sync()
            except (OSError, ValueError):
                self.offline.message = 'Sync paused: local storage could not be updated. Your saved changes are retained.'
                return 0
        future = self.executor.submit(work)
        future.add_done_callback(lambda result: self.results.put((result, done, True)))
        self.emit()

    @Slot()
    def syncNow(self):
        if self.offline:
            self.offline.last_refresh = 0
            self.next_sync = 0
            self.syncOffline()

    @Slot()
    def showSync(self):
        self.connectionSection(True)
        self.show_panel('settings')

    @Slot(str)
    def discardQueued(self, qid):
        if not self.offline or self._s['busy'] or self.syncing:
            return
        problem = next((o for o in self.offline.status()['problems'] if o['id'] == qid), None)
        if not problem:
            return
        def discard():
            def done(_):
                self.month_valid, self.month_loaded = False, None
                self.toast.emit('Local change discarded. FreshBooks was not changed.')
                self.next_sync = 0
                self.emit()
            self.run('review', lambda: self.offline.resolve(qid, 'discard'), done)
        self.confirm('First review this entry in FreshBooks. Discard this local change and keep the FreshBooks version? If a submission was interrupted, it may already exist there. Nothing will be resubmitted or deleted by this action.', discard, 'Review saved change')

    @Slot()
    def checkPending(self):
        def checked(result):
            if result and result.get('deleted'):
                self.deleted_entry(result)
                return
            if result and result.get('unresolved'):
                self.error.emit('The pending operation is unresolved. Review your entries in FreshBooks before releasing it. Nothing was retried.')
            else:
                self.toast.emit('Entry confirmed' if result else 'No pending saves')
                if result:
                    for scope in self.forms:
                        form = self.forms[scope]
                        try:
                            args = (form['client'], form['day'], form['hours'], form['note'], form['billable'], self.profile['id'], form['project'], form['service'])
                            payload = edit_payload(self.originals[scope], *args) if self.originals[scope] else entry_payload(*args)
                            if matching_entry(payload['time_entry'], result):
                                self.reset_form(scope, entry_date(result))
                        except (ValueError, KeyError):
                            pass
                    self.month_valid = False
                    if self._s['panel'] == 'month':
                        self.load_month(force=True)
        self.run('pending', self.api.check_pending, checked)

    @Slot()
    def releasePending(self):
        if self._s['busy']:
            return
        if self.offline and self.offline.status()['count'] and not self.offline.legacy_pending():
            self.error.emit('Review the queued changes below instead. They are retained until resolved.')
            return
        if not self.vault.get('pending'):
            self.toast.emit('No pending saves')
            return
        def release():
            try:
                self.vault.update(pending=None)
                self.toast.emit('Pending guard released. No time was submitted.')
            except OSError as exc:
                self.error.emit(str(exc))
        self.confirm('Only release after reviewing FreshBooks for this entry. Releasing the guard can allow a duplicate if the previous save succeeded. Release it?', release)

    def apply_window_flags(self):
        if self.window:
            visible = self.window.isVisible()
            self.window.setFlag(Qt.WindowStaysOnTopHint, bool(self.prefs.data['always_on_top'] or self.prefs.data['docked_mode']))
            self.window.setFlag(Qt.Tool, bool(self.prefs.data['docked_mode']))
            if visible:
                self.window.show()

    @Slot()
    def testReminder(self):
        self.deliver_reminder()

    @Slot()
    def reminderOpened(self):
        if self.prefs.data.get('popup_sound',True):
            key = 'remind_me_sound_choice' if self.reminder_is_followup else 'popup_sound_choice'
            self.popup_chime.play(self.prefs.data.get(key,'ethereal'), self.prefs.data.get('popup_volume',60))

    @Slot()
    def previewSound(self):
        if self.prefs.data.get('popup_sound', True):
            self.popup_chime.play(self.prefs.data.get('popup_sound_choice', 'ethereal'), self.prefs.data.get('popup_volume', 60))

    @Slot()
    def previewRemindMeSound(self):
        if self.prefs.data.get('popup_sound', True):
            self.popup_chime.play(self.prefs.data.get('remind_me_sound_choice', 'ethereal'), self.prefs.data.get('popup_volume', 60))

    @Slot(result=bool)
    def remindMe(self):
        try:
            self.delayed_reminder.schedule(self.prefs.data.get('remind_me_minutes',15))
            self.arm_delayed_reminder()
            return True
        except (ValueError,OSError) as exc:
            self.error.emit(str(exc))
            return False

    def arm_delayed_reminder(self):
        remaining=self.delayed_reminder.remaining()
        if remaining is None:
            self.delay_timer.stop()
        else:
            self.delay_timer.start(min(2147483647,max(0,int(remaining*1000)+1)))

    def deliver_delayed_reminder(self):
        if self.delayed_reminder.consume():
            self.delay_timer.stop()
            self.deliver_reminder(force_popup=True, followup=True)
            return True
        self.arm_delayed_reminder()
        return False

    def deliver_reminder(self, force_popup=False, followup=False):
        self.reminder_is_followup = followup
        # This is an app-owned window, independent of Windows toast permissions/DND.
        if force_popup or self.prefs.data.get('reminder_popup', True):
            self.reminder.emit()
        if self.tray:
            try:
                self.tray.showMessage('Time to log your hours', 'Open FreshTray to record your time.', QSystemTrayIcon.Information, 10000)
            except (RuntimeError, OSError):
                pass  # A missing/broken notification service must not block the popup.

    def tick(self):
        delayed = self.deliver_delayed_reminder()
        now = datetime.now()
        day = now.date().isoformat()
        if day != self.last_delivered and reminder_due(self.prefs.data, now):
            self.last_delivered = day
            try:
                self.prefs.save(last_reminded=day)
            except OSError:
                pass  # Per-process guard still prevents duplicate delivery.
            if not delayed:
                self.deliver_reminder()

    @Slot()
    def logFromReminder(self):
        self.show_panel('log')

    @Slot()
    def closeRequested(self):
        if self.prefs.data.get('close_to_tray', True) and self.tray and self.tray.isSystemTrayAvailable():
            if self.window:
                self.window.hide()
        else:
            self.requestQuit()

    @Slot()
    def requestQuit(self):
        if self._s['busy']:
            self.error.emit('Wait for the current operation to finish before quitting.')
            if self.window:
                self.window.show()
            return
        if any(self.dirty(scope) for scope in self.forms):
            if self.window:
                self.window.show()
            self.confirm('Quit FreshTray and discard unsaved entry drafts?', self.shutdown)
        else:
            self.shutdown()

    def shutdown(self):
        if self.offline:
            self.offline.stopping.set()
        self.popup_chime.close()
        self.timer.stop()
        self.sync_timer.stop()
        self.reminder_timer.stop()
        self.delay_timer.stop()
        if self.tray:
            self.tray.hide()
        self.local_executor.shutdown(wait=False, cancel_futures=True)
        self.executor.shutdown(wait=False, cancel_futures=True)
        QApplication.instance().quit()

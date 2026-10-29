"""An independent day-entry draft embedded in the monthly calendar page."""
from copy import deepcopy
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox

from .components import FieldPair, WrapLabel, field_label, note_field
from .components import CalendarIcon
from .widgets import CalendarPicker
from .model import entry_payload, matching_entry
from .history_model import edit_payload, entry_date, hours_input, format_duration, edit_restriction


def index_of(items, ident):
    return next((i for i, item in enumerate(items)
                 if str(item.get('id', item.get('userid'))) == str(ident)), -1)


class MonthlyEditor(ttk.Frame):
    def __init__(self, history, parent):
        super().__init__(parent, style='CardBody.TFrame')
        self.history, self.app = history, history.app
        self.original, self.baseline = None, None
        self.clients = deepcopy(self.app.clients)
        self.projects = deepcopy(self.app.projects)
        self.services = deepcopy(self.app.services)
        self.filtered_projects, self.filtered_services = [], []
        self.title = tk.StringVar(value='Add time for this day')
        ttk.Label(self, textvariable=self.title, style='Section.TLabel').pack(anchor='w', pady=(0, 5))
        self.notice = tk.StringVar(value='')
        WrapLabel(self, textvariable=self.notice, style='CardMuted.TLabel').pack(fill='x', pady=(0, 5))
        pair = FieldPair(self)
        field_label(pair.left, 'Client')
        self.client_combo = ttk.Combobox(pair.left, state='readonly', width=18)
        self.client_combo.pack(fill='x')
        self.client_combo.bind('<<ComboboxSelected>>', lambda _: self.filter_projects())
        field_label(pair.right, 'Hours · H:MM or decimal')
        self.hours = tk.StringVar(value='8:00')
        self.hours_entry = ttk.Entry(pair.right, textvariable=self.hours, width=10)
        self.hours_entry.pack(fill='x')
        pair = FieldPair(self)
        field_label(pair.left, 'Project · optional')
        self.project_combo = ttk.Combobox(pair.left, state='readonly', width=16)
        self.project_combo.pack(fill='x')
        self.project_combo.bind('<<ComboboxSelected>>', lambda _: self.filter_services())
        field_label(pair.right, 'Service · optional')
        self.service_combo = ttk.Combobox(pair.right, state='readonly', width=16)
        self.service_combo.pack(fill='x')
        pair = FieldPair(self)
        field_label(pair.left, 'Entry date')
        self.day = tk.StringVar(value=history.selected_day.isoformat())
        date_row = ttk.Frame(pair.left, style='CardBody.TFrame')
        date_row.pack(fill='x')
        date_row.columnconfigure(0, weight=1)
        self.date_entry = ttk.Entry(date_row, textvariable=self.day, width=12)
        self.date_entry.grid(row=0, column=0, sticky='ew')
        self.calendar_button = CalendarIcon(date_row, self.open_calendar)
        self.calendar_button.grid(row=0, column=1, padx=(7, 0))
        self.date_entry.bind('<Alt-Down>', lambda _: self.open_calendar())
        field_label(pair.right, 'Billing')
        self.billable = tk.BooleanVar(value=True)
        self.billable_check = ttk.Checkbutton(pair.right, text='Billable', variable=self.billable)
        self.billable_check.pack(anchor='w')
        field_label(self, 'What did you work on?')
        self.note = note_field(self, height=3)
        buttons = ttk.Frame(self, style='CardBody.TFrame')
        buttons.pack(fill='x', pady=(8, 0))
        self.cancel_button = ttk.Button(buttons, text='Clear form', command=self.clear)
        self.cancel_button.pack(side='left')
        self.save_button = ttk.Button(buttons, text='Log time', style='Accent.TButton', command=self.submit)
        self.save_button.pack(side='right')
        self.controls = [self.client_combo, self.project_combo, self.service_combo, self.hours_entry,
                         self.date_entry, self.calendar_button, self.billable_check, self.note,
                         self.cancel_button, self.save_button]
        self.client_combo['values'] = [self.app.label_client(c) for c in self.clients]
        if self.clients:
            self.client_combo.current(max(0, index_of(self.clients, self.app._form_state()[1])))
        self.filter_projects()
        self.reset_for_day(history.selected_day)

    def state(self):
        def chosen(combo, items):
            index = combo.current()
            return items[index].get('id', items[index].get('userid')) if 0 <= index < len(items) else None
        return (chosen(self.client_combo, self.clients), chosen(self.project_combo, [{}]+self.filtered_projects),
                chosen(self.service_combo, [{}]+self.filtered_services), self.day.get(), self.hours.get(),
                self.note.get('1.0', 'end-1c'), self.billable.get())

    def dirty(self):
        return self.baseline is not None and self.state() != self.baseline

    def confirm_discard(self):
        return not self.dirty() or messagebox.askyesno('Unsaved monthly entry',
            'Discard the unsaved changes in the monthly entry form?', parent=self.app.root)

    def reset_for_day(self, day):
        self.original = None
        self.day.set(day.isoformat())
        self.hours.set('8:00')
        self.note.configure(state='normal')
        self.note.delete('1.0', 'end')
        self.billable.set(True)
        self.title.set('Add time for ' + day.strftime('%B %d, %Y'))
        self.notice.set('')
        self.save_button.configure(text='Preview entry' if self.app.demo else 'Log time  ✓')
        self.cancel_button.configure(text='Clear form')
        self.baseline = self.state()
        self.update_enabled()

    def clear(self):
        if not self.app.busy and self.confirm_discard():
            self.reset_for_day(self.history.selected_day)

    def filter_projects(self):
        ci = self.client_combo.current()
        cid = self.clients[ci].get('id', self.clients[ci].get('userid')) if ci >= 0 else None
        self.filtered_projects = [p for p in self.projects if str(p.get('client_id')) == str(cid)]
        self.project_combo['values'] = ['No project']+[p['title'] for p in self.filtered_projects]
        self.project_combo.current(0)
        self.filter_services()

    def filter_services(self):
        pi = self.project_combo.current()-1
        self.filtered_services = self.filtered_projects[pi].get('services', []) if pi >= 0 else self.services
        self.service_combo['values'] = ['No service']+[s['name'] for s in self.filtered_services]
        self.service_combo.current(0)

    def load_entry(self, entry):
        restriction = edit_restriction(entry)
        if restriction:
            raise ValueError(restriction)
        if str(entry.get('identity_id', self.history.profile['id'])) != str(self.history.profile['id']):
            raise ValueError('Only your own time entries can be edited here.')
        cid, pid, sid = entry['client_id'], entry.get('project_id'), entry.get('service_id')
        if index_of(self.clients, cid) < 0:
            self.clients.append({'id': cid, 'organization': 'Existing client'})
        if pid and index_of(self.projects, pid) < 0:
            self.projects.append({'id': pid, 'client_id': cid, 'title': 'Existing project', 'services': []})
        if pid:
            project = self.projects[index_of(self.projects, pid)]
            if str(project.get('client_id')) != str(cid):
                raise ValueError("The entry's project now belongs to a different client. Review it in FreshBooks.")
        self.client_combo['values'] = [self.app.label_client(c) for c in self.clients]
        self.client_combo.current(index_of(self.clients, cid))
        self.filter_projects()
        if pid:
            self.project_combo.current(index_of(self.filtered_projects, pid)+1)
            self.filter_services()
        if sid and index_of(self.filtered_services, sid) < 0:
            # Keep the exact historical assignment without borrowing another service.
            self.filtered_services = list(self.filtered_services)+[{'id': sid, 'name': 'Existing service'}]
            self.service_combo['values'] = ['No service']+[s['name'] for s in self.filtered_services]
        if sid:
            self.service_combo.current(index_of(self.filtered_services, sid)+1)
        self.original = deepcopy(entry)
        self.day.set(entry_date(entry).isoformat())
        self.hours.set(hours_input(entry.get('duration')))
        self.note.configure(state='normal')
        self.note.delete('1.0', 'end')
        self.note.insert('1.0', entry.get('note') or '')
        self.billable.set(bool(entry.get('billable')))
        self.title.set('Edit time for ' + entry_date(entry).strftime('%B %d, %Y'))
        self.notice.set('Already billed. Billing status is retained; review the related invoice in FreshBooks after changing time.'
                        if entry.get('billed') else 'Save changes updates this entry without adding another.')
        self.save_button.configure(text='Preview changes' if self.app.demo else 'Save changes  ✓')
        self.cancel_button.configure(text='Cancel edit')
        self.baseline = self.state()
        self.update_enabled()

    def update_enabled(self):
        enabled = self.history.data_loaded and not self.app.busy and self.history.selected_day <= date.today()
        for control in self.controls:
            control.configure(state=('readonly' if isinstance(control, ttk.Combobox) else 'normal') if enabled else 'disabled')

    def open_calendar(self):
        if self.app.busy:
            return
        if self.app.calendar_window and self.app.calendar_window.winfo_exists():
            self.app.calendar_window.close()
        try:
            selected = date.fromisoformat(self.day.get())
        except ValueError:
            selected = date.today()
        self.app.calendar_window = CalendarPicker(self.date_entry, min(selected, date.today()), self.day.set)
        self.app.apply_topmost()
        self.app.appearance.repaint()

    def payload(self):
        ci = self.client_combo.current()
        if ci < 0:
            raise ValueError('Choose a client before saving time.')
        client = self.clients[ci]
        pi, si = self.project_combo.current()-1, self.service_combo.current()-1
        args = (client.get('id', client.get('userid')), self.day.get(), self.hours.get(),
                self.note.get('1.0', 'end-1c'), self.billable.get(), self.history.profile['id'],
                self.filtered_projects[pi]['id'] if pi >= 0 else None,
                self.filtered_services[si]['id'] if si >= 0 else None)
        return edit_payload(self.original, *args) if self.original else entry_payload(*args)

    def submit(self):
        app, history = self.app, self.history
        if app.busy or not history.data_loaded:
            return
        try:
            if str(app.selected_business()['id']) != str(history.business['id']) or str(app.profile_data['id']) != str(history.profile['id']):
                raise ValueError('The connected business changed. Reload the monthly view before saving.')
            payload = self.payload()
            original, bid = deepcopy(self.original), history.business['id']
            previous = app.vault.get('last_success')
            if not original and previous and previous['business_id'] == bid and previous['payload'] == payload:
                if not messagebox.askyesno('Possible duplicate', 'This exact entry was already saved. Add another copy?', parent=app.root):
                    return
        except ValueError as exc:
            self.notice.set(str(exc))
            messagebox.showerror('Check your entry', str(exc), parent=app.root)
            return

        def saved(entry):
            text = ('Preview complete. No time was sent.' if app.demo else
                    ('Updated' if original else 'Saved to FreshBooks')+' • '+format_duration(payload['time_entry']['duration'])+' hours')
            if not app.demo:
                app.tray.notify('Time updated' if original else 'Time logged', 'Your time entry was saved to FreshBooks.')
            history.saved_entry(entry, text)

        work = (lambda: app.api.update_entry(bid, original['id'], payload, original)) if original else lambda: app.api.submit(bid, payload)
        app.run(work, saved, 'Previewing…' if app.demo else ('Updating your time entry…' if original else 'Saving your time entry…'),
                on_error=self.notice.set)

    def reconcile(self, entry):
        try:
            if entry and matching_entry(self.payload()['time_entry'], entry):
                self.reset_for_day(entry_date(entry))
                return True
        except ValueError:
            pass
        return False

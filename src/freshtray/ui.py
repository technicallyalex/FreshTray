from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from .api import ApiError, OAuthAttempt, DEFAULT_REDIRECT
from .model import entry_payload, reminder_due
from .windows import Tray, startup_enabled, set_startup
from .widgets import CalendarPicker, ReminderTime
from .history import MonthlyView
from .appearance import Appearance
from .layout import build_shell
from .components import ScrollPage
from .sizing import LaunchFit
from .docking import DockedMode
from .history_model import edit_payload, entry_date, hours_input, format_duration, edit_restriction

BG = "#F3F6FA"
INK = "#16324F"
MUTED = "#586B80"
GREEN = "#087F5B"


class App:
    def __init__(self, root, api, vault, preferences, assets, launcher, demo=False):
        self.root, self.api, self.vault, self.prefs = root, api, vault, preferences
        self.launcher, self.demo = launcher, demo
        self.events = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.busy, self.attempt, self.settings_window = False, None, None
        self.calendar_window = None
        self.history_window = None
        self.was_maximized = False
        self.editing_entry, self.edit_business_id, self.form_baseline = None, None, None
        self.profile_data, self.businesses = {}, []
        self.clients, self.projects, self.services, self.filtered_projects = [], [], [], []
        self.filtered_services = []
        self.buttons = []
        self.last_date = date.today()
        self.root.title("FreshTray" + (" — Offline preview" if demo else ""))
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.iconbitmap(str(assets / "freshtray.ico"))
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.appearance = Appearance(root, preferences.data["theme"])
        self.build()
        self.launch_fit = LaunchFit(self)
        self.docking = DockedMode(self)
        self.docking.apply()
        self.apply_topmost()
        self.tray = Tray(self.events, assets / "freshtray.ico")
        root.after(150, self.poll)
        root.after(1000, self.tick)
        if self.api.connected:
            self.load_profile()
        else:
            self.status.set("Connect FreshBooks in Settings to load your clients.")
            self.launch_fit.ready()

    def button(self, parent, text, command, accent=False):
        button = ttk.Button(parent, text=text, command=command, style="Accent.TButton" if accent else "TButton")
        self.buttons.append(button)
        return button

    def label(self, parent, text, row, column=0):
        ttk.Label(parent, text=text, style="Muted.TLabel").grid(row=row, column=column, sticky="w", pady=(14, 5))

    def build(self):
        build_shell(self)

    def select_page(self, name):
        changed = getattr(self, "active_page", None) != name
        if changed and hasattr(self, "chrome"):
            self.chrome.freeze()
        self.active_page = name
        self.page_host.select(self.pages[name])
        for key in self.pages:
            self.nav_buttons[key].configure(style="NavActive.TButton" if key == name else "Nav.TButton")
        self.pages[name].activate()
        if changed and hasattr(self, "launch_fit"):
            self.launch_fit.pending = True
            self.launch_fit.schedule()
        if changed and hasattr(self, "chrome"):
            self.root.after(30, self.finish_panel_transition)

    def close_window(self):
        if self.prefs.data.get("close_to_tray", True):
            self.hide()
        else:
            self.quit()

    def finish_panel_transition(self):
        self.chrome.thaw()

    def refresh_pages(self, event=None):
        for page in self.pages.values():
            page.sync()
        self.pages[self.active_page].activate()

    def show_entry(self):
        self.select_page("entry")
        self.show()

    def scroll_page(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if isinstance(widget, (tk.Text, ttk.Treeview, ttk.Combobox, ttk.Spinbox)):
            return
        while widget is not None:
            if isinstance(widget, ScrollPage):
                if widget.canvas.yview() != (0.0, 1.0):
                    widget.canvas.yview_scroll(-int(event.delta / 120), "units")
                    return "break"
                return
            widget = getattr(widget, "master", None)


    def _form_state(self):
        def chosen(combo, values):
            index = combo.current()
            return values[index].get("id", values[index].get("userid")) if 0 <= index < len(values) else None
        return (chosen(self.business_combo, self.businesses), chosen(self.client_combo, self.clients),
                chosen(self.project_combo, [{}] + self.filtered_projects),
                chosen(self.service_combo, [{}] + self.filtered_services), self.day.get(), self.hours.get(),
                self.note.get("1.0", "end-1c"), self.billable.get(),
                self.editing_entry.get("id") if self.editing_entry else None)

    def confirm_replace_form(self):
        if self.form_baseline is not None and self._form_state() != self.form_baseline:
            return messagebox.askyesno("Unsaved form", "Replace the unsaved changes in the entry form?", parent=self.root)
        return True

    def clear_edit_mode(self):
        self.editing_entry, self.edit_business_id = None, None
        self.form_title.set("Log your day")
        self.edit_bar.pack_forget()
        self.save_button.configure(text="Preview entry" if self.demo else "Log time  ✓")
        self.business_combo.configure(state="disabled" if self.busy else "readonly")

    def cancel_edit(self, confirm=True):
        if confirm and not self.confirm_replace_form():
            return
        self.clear_edit_mode()
        self.note.delete("1.0", "end")
        self.day.set(date.today().isoformat())
        self.hours.set("8:00")
        self.billable.set(True)
        self.form_baseline = self._form_state()

    def open_history(self):
        self.select_page("history")
        self.show()
        if self.busy:
            return
        if not self.profile_data or not self.businesses:
            self.load_profile()
            return
        business = self.selected_business()
        if self.history_window and self.history_window.winfo_exists():
            if self.history_window.business["id"] != business["id"] or self.history_window.profile["id"] != self.profile_data["id"]:
                self.history_window.destroy()
            else:
                if not self.history_window.data_loaded:
                    self.history_window.refresh()
                return
        self.history_window = MonthlyView(self, business, self.profile_data)
        self.history_window.pack(fill="both", expand=True)
        self.appearance.repaint()
        self.history_window.refresh()


    def add_for_day(self, day, business_id):
        if self.busy or self.selected_business()["id"] != business_id or not self.confirm_replace_form():
            return
        self.cancel_edit(confirm=False)
        self.day.set(day.isoformat())
        self.form_baseline = self._form_state()
        self.status.set("New entry for " + day.isoformat() + ". Choose the client, hours and note.")
        self.show()
        self.select_page("entry")
        self.pages["entry"].top()
        self.note.focus_set()

    def begin_edit_entry(self, entry, business_id):
        restriction = edit_restriction(entry)
        if restriction:
            raise ValueError(restriction)
        if self.selected_business()["id"] != business_id:
            raise ValueError("The selected business changed. Open its calendar again.")
        if str(entry.get("identity_id", self.profile_data["id"])) != str(self.profile_data["id"]):
            raise ValueError("Only your own time entries can be edited here.")
        cid, pid, sid = entry["client_id"], entry.get("project_id"), entry.get("service_id")
        def index_of(values, ident):
            return next((i for i, item in enumerate(values) if str(item.get("id", item.get("userid"))) == str(ident)), -1)
        ci = index_of(self.clients, cid)
        if ci < 0:
            self.clients.append({"id": cid, "organization": "Existing client"})
            ci = len(self.clients) - 1
        self.client_combo["values"] = [self.label_client(c) for c in self.clients]
        self.client_combo.current(ci)
        if pid and index_of(self.projects, pid) < 0:
            self.projects.append({"id": pid, "client_id": cid, "title": "Existing project", "services": []})
        if sid and index_of(self.services, sid) < 0:
            self.services.append({"id": sid, "name": "Existing service"})
        if pid:
            project = self.projects[index_of(self.projects, pid)]
            if str(project.get("client_id")) != str(cid):
                raise ValueError("The entry's project now belongs to a different client. Review it in FreshBooks.")
            if sid and index_of(project.get("services", []), sid) < 0:
                service = self.services[index_of(self.services, sid)]
                project["services"] = list(project.get("services", [])) + [service]
        self.filter_projects()
        if pid:
            self.project_combo.current(index_of(self.filtered_projects, pid) + 1)
            self.filter_services()
        if sid:
            self.service_combo.current(index_of(self.filtered_services, sid) + 1)
        self.editing_entry, self.edit_business_id = deepcopy(entry), business_id
        self.day.set(entry_date(entry).isoformat())
        self.hours.set(hours_input(entry.get("duration")))
        self.note.delete("1.0", "end")
        self.note.insert("1.0", entry.get("note") or "")
        self.billable.set(bool(entry.get("billable")))
        self.form_title.set("Edit logged time")
        self.edit_caption.set("Editing time for " + self.day.get())
        self.edit_bar.pack(fill="x", pady=(10, 0), before=self.footer)
        self.save_button.configure(text="Preview changes" if self.demo else "Save changes  ✓")
        self.business_combo.configure(state="disabled")
        self.form_baseline = self._form_state()
        self.status.set("Change the entry, then choose Save changes. No new entry will be created.")
        self.select_page("entry")
        self.pages["entry"].top()
        self.show()


    def open_calendar(self):
        if self.busy:
            return
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.lift()
            return
        try:
            selected = date.fromisoformat(self.day.get())
        except ValueError:
            selected = date.today()
        self.calendar_window = CalendarPicker(self.date_entry, min(selected, date.today()), self.day.set)
        self.apply_topmost()
        self.appearance.repaint()

    def set_busy(self, value):
        self.busy = value
        if value and self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.close()
        self.buttons = [b for b in self.buttons if b.winfo_exists()]
        for button in self.buttons:
            button.configure(state="disabled" if value else "normal")
        for control in self.form_controls:
            normal = "readonly" if isinstance(control, ttk.Combobox) else "normal"
            control.configure(state="disabled" if value else normal)
        if self.editing_entry:
            self.business_combo.configure(state="disabled")
        if self.history_window and self.history_window.winfo_exists():
            self.history_window.set_busy(value)

    def run(self, work, done, message, on_error=None):
        if self.busy:
            return
        self.set_busy(True)
        self.status.set(message)
        future = self.executor.submit(work)
        future.add_done_callback(lambda completed: self.events.put(("result", (completed, done, on_error))))

    def poll(self):
        for _ in range(30):
            try:
                event, value = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "result":
                future, done, on_error = value
                self.set_busy(False)
                try:
                    done(future.result())
                except Exception as exc:
                    # Only approved, sanitized messages are shown; never raw network data.
                    text = str(exc) if isinstance(exc, (ApiError, ValueError)) else "Could not complete the action. Check local storage and try again."
                    if self.vault.get("pending"):
                        text += " A submission is pending: use Check pending before adding more time."
                    self.status.set(text)
                    if on_error:
                        on_error(text)
                    self.show()
                    messagebox.showerror("FreshTray", text, parent=self.root)
            elif event == "show":
                self.show()
            elif event == "history":
                self.open_history()
            elif event == "settings":
                self.settings()
            elif event == "notify":
                self.tray.notify()
            elif event == "quit":
                self.quit()
                return
            elif event == "tray_error":
                self.show()
                self.status.set(value)
        self.root.after(150, self.poll)

    def load_profile(self):
        if self.busy:
            return
        if self.editing_entry:
            if not self.confirm_replace_form():
                return
            self.cancel_edit(confirm=False)
        def loaded(profile):
            self.profile_data = profile
            self.connection_text.set("Connected · " + " ".join(filter(None, [profile.get("first_name"), profile.get("last_name")])))
            self.businesses = [m["business"] for m in profile.get("business_memberships", [])
                               if m.get("role") != "client" and m.get("business", {}).get("account_id")
                               and m["business"].get("active", True)]
            self.business_combo["values"] = [b["name"] for b in self.businesses]
            if not self.businesses:
                self.launch_fit.ready()
                self.status.set("No eligible FreshBooks business. Check your membership and permissions.")
                return
            chosen = next((i for i, b in enumerate(self.businesses) if b["id"] == self.prefs.data.get("business_id")), 0)
            self.business_combo.current(chosen)
            self.load_catalog()
        if not self.api.connected:
            self.settings()
            return
        self.run(self.api.profile, loaded, "Loading your FreshBooks businesses…", on_error=lambda _: self.launch_fit.ready())

    def selected_business(self):
        index = self.business_combo.current()
        if index < 0 or index >= len(self.businesses):
            raise ValueError("Select a FreshBooks business first.")
        return self.businesses[index]

    @staticmethod
    def label_client(client):
        name = client.get("organization") or " ".join(filter(None, [client.get("fname"), client.get("lname")])) or "Unnamed client"
        return name

    def load_catalog(self):
        if self.busy:
            return
        business = self.selected_business()
        if self.history_window and self.history_window.winfo_exists() and not self.history_window.editor.confirm_discard():
            previous = next((i for i, b in enumerate(self.businesses) if b["id"] == self.history_window.business["id"]), -1)
            if previous >= 0:
                self.business_combo.current(previous)
            return
        self.clients, self.projects, self.services = [], [], []
        for combo in [self.client_combo, self.project_combo, self.service_combo]:
            combo.set("")
            combo["values"] = []
        def loaded(result):
            self.clients, self.projects, self.services, warnings = result
            self.prefs.save(business_id=business["id"])
            self.client_combo["values"] = [self.label_client(c) for c in self.clients]
            if self.clients:
                self.client_combo.current(0)
            self.filter_projects()
            self.form_baseline = self._form_state()
            if self.history_window and self.history_window.winfo_exists():
                self.history_window.destroy()
                self.history_window = None
            self.launch_fit.ready()
            if self.active_page == "history":
                self.open_history()
            self.status.set(" ".join(warnings) if warnings else (
                "A previous submission needs checking. Use Check pending." if self.vault.get("pending")
                else "Ready. Entries are logged as the connected FreshBooks user."))
        self.run(lambda: self.api.catalog(business), loaded, "Loading clients, projects and services…", on_error=lambda _: self.launch_fit.ready())

    def filter_projects(self):
        index = self.client_combo.current()
        cid = self.clients[index].get("id", self.clients[index].get("userid")) if index >= 0 else None
        self.filtered_projects = [p for p in self.projects if str(p.get("client_id")) == str(cid)]
        self.project_combo["values"] = ["No project"] + [p["title"] for p in self.filtered_projects]
        self.project_combo.current(0)
        self.filter_services()

    def filter_services(self):
        index = self.project_combo.current() - 1
        if index >= 0:
            self.filtered_services = self.filtered_projects[index].get("services", [])
        else:
            self.filtered_services = self.services
        self.service_combo["values"] = ["No service"] + [s["name"] for s in self.filtered_services]
        self.service_combo.current(0)

    def submit(self):
        if self.busy:
            return
        try:
            business = self.selected_business()
            index = self.client_combo.current()
            if index < 0:
                raise ValueError("Choose a client. Use Settings to connect or Reload lists.")
            client = self.clients[index]
            pi, si = self.project_combo.current() - 1, self.service_combo.current() - 1
            args = (client.get("id", client.get("userid")), self.day.get(), self.hours.get(),
                    self.note.get("1.0", "end-1c"), self.billable.get(), self.profile_data["id"],
                    self.filtered_projects[pi]["id"] if pi >= 0 else None,
                    self.filtered_services[si]["id"] if si >= 0 else None)
            original = deepcopy(self.editing_entry)
            if original:
                if self.edit_business_id != business["id"]:
                    raise ValueError("Choose the original business before saving this entry.")
                payload = edit_payload(original, *args)
            else:
                payload = entry_payload(*args)
                previous = self.vault.get("last_success")
                if previous and previous["business_id"] == business["id"] and previous["payload"] == payload:
                    if not messagebox.askyesno("Possible duplicate", "This exact entry was already saved. Add another copy?", parent=self.root):
                        return
        except ValueError as exc:
            messagebox.showerror("Check your entry", str(exc), parent=self.root)
            return

        def saved(entry):
            text = ("Preview complete. No time was sent." if self.demo else
                    f'{"Updated" if original else "Saved to FreshBooks"} • {format_duration(payload["time_entry"]["duration"])} hours')
            if original:
                self.cancel_edit(confirm=False)
            elif not self.demo:
                self.note.delete("1.0", "end")
            self.form_baseline = self._form_state()
            self.status.set(text)
            if not self.demo:
                self.tray.notify("Time updated" if original else "Time logged", "Your time entry was saved to FreshBooks.")
            if self.history_window and self.history_window.winfo_exists():
                self.history_window.refresh(saved_status=text)

        work = (lambda: self.api.update_entry(business["id"], original["id"], payload, original)) if original else (
               lambda: self.api.submit(business["id"], payload))
        self.run(work, saved, "Previewing…" if self.demo else ("Updating your time entry…" if original else "Saving your time entry…"))


    def check_pending(self):
        def checked(result):
            if result and result.get("unresolved"):
                messagebox.showwarning("Submission needs review", f'{result["matches"]} matching entries found. Nothing was retried.\nReview FreshBooks before releasing the pending entry in Settings.', parent=self.root)
                self.status.set("Pending entry kept safely. Review FreshBooks, then use Settings.")
            else:
                self.status.set("Confirmed the entry was saved." if result else "No pending submissions.")
                if result and self.editing_entry and str(self.editing_entry["id"]) == str(result["id"]):
                    self.cancel_edit(confirm=False)
                if self.history_window and self.history_window.winfo_exists():
                    success = self.vault.get("last_success") or {}
                    if success.get("business_id") == self.history_window.business["id"] and self.history_window.editor.reconcile(result):
                        self.history_window.saved_entry(result, self.status.get())
                    else:
                        self.history_window.refresh(saved_status=self.status.get())
        self.run(self.api.check_pending, checked, "Checking FreshBooks for the pending entry…")

    def settings(self):
        self.select_page("settings")
        self.show()

    def apply_topmost(self):
        enabled = bool(self.prefs.data["always_on_top"] or self.prefs.data.get("docked_mode"))
        self.root.attributes("-topmost", enabled)
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.attributes("-topmost", enabled)

    def show(self):
        # Preserve user-resized dimensions and position when switching pages/restoring.
        if self.root.state() in ("withdrawn", "iconic"):
            self.root.deiconify()
            if self.was_maximized:
                self.root.state("zoomed")
        self.launch_fit.schedule()
        if self.docking.enabled:
            self.root.after_idle(self.docking.position)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, self.apply_topmost)

    def remember_size(self):
        if self.root.state() == "normal":
            try:
                self.prefs.save(window_size=[self.root.winfo_width(), self.root.winfo_height()])
            except OSError:
                self.status.set("Could not save window size.")

    def hide(self):
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.close()
        self.was_maximized = self.root.state() == "zoomed"
        self.remember_size()
        self.root.withdraw()


    def tick(self):
        self.appearance.refresh_system()
        now = datetime.now()
        if now.date() != self.last_date:
            if not self.note.get("1.0", "end-1c").strip() and self.day.get() == self.last_date.isoformat():
                self.day.set(now.date().isoformat())
            self.last_date = now.date()
        if reminder_due(self.prefs.data, now):
            try:
                self.prefs.save(last_reminded=now.date().isoformat())
                self.tray.notify()
            except OSError:
                self.status.set("Could not save reminder state. Check local storage.")
        self.root.after(15000, self.tick)

    def quit(self):
        if self.busy:
            messagebox.showinfo("FreshTray", "Wait for the current action to finish before quitting.", parent=self.root)
            return
        monthly_draft = self.history_window and self.history_window.winfo_exists() and self.history_window.editor.dirty()
        if (self.note.get("1.0", "end-1c").strip() or (self.form_baseline is not None and self._form_state() != self.form_baseline) or monthly_draft) and not self.demo:
            self.show()
            if not messagebox.askyesno("Unsaved changes", "Quit and discard unsaved changes? Choose Cancel to keep working.", parent=self.root):
                return
        self.remember_size()
        self.tray.close()
        self.executor.shutdown(wait=False)
        self.root.destroy()

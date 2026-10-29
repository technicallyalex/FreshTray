"""Single-window shell, entry page and docked Settings page."""
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from datetime import date

from .components import ScrollPage, WrapLabel, FieldPair, card, field_label, note_field
from .components import CalendarIcon
from .widgets import ReminderTime
from .chrome import WindowChrome
from .api import OAuthAttempt, DEFAULT_REDIRECT
from .windows import startup_enabled, set_startup


def build_shell(app):
    root = app.root
    root.columnconfigure(0, weight=1)
    root.rowconfigure(2, weight=1)
    app.nav_buttons = {}
    header = ttk.Frame(root, style="Header.TFrame", padding=(16, 8))
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)
    ttk.Label(header, text="FreshTray", style="Brand.TLabel").grid(row=0, column=0, sticky="w")
    app.connection_text = tk.StringVar(value="FreshBooks time tracking")
    nav = ttk.Frame(root, padding=(14, 5))
    nav.grid(row=1, column=0, sticky="ew")
    for key, title, command in [("entry", "Log time", app.show_entry), ("history", "Monthly hours", app.open_history),
                                ("settings", "Settings", app.settings)]:
        button = ttk.Button(nav, text=title, command=command, style="Nav.TButton")
        button.pack(side="left", padx=(0, 5))
        app.nav_buttons[key] = button
    if app.demo:
        ttk.Label(nav, text="OFFLINE PREVIEW", style="Warning.TLabel").pack(side="right", padx=6)
    app.page_host = ttk.Notebook(root, style="Pages.TNotebook")
    app.page_host.grid(row=2, column=0, sticky="nsew")
    app.page_host.columnconfigure(0, weight=1)
    app.page_host.rowconfigure(0, weight=1)
    app.pages = {key: ScrollPage(app.page_host, min_width=740 if key == "history" else 520)
                 for key in ("entry", "history", "settings")}
    for name, page in app.pages.items():
        app.page_host.add(page, text=name)
    app.history_host = app.pages["history"].body
    app.history_host.columnconfigure(0, weight=1)
    build_entry(app, app.pages["entry"].body)
    # Build once: switching pages never discards an OAuth attempt or typed form.
    app.settings_window = SettingsPanel(app, app.pages["settings"].body)
    app.settings_window.pack(fill="both", expand=True)
    app.status = tk.StringVar(value="Loading…")
    WrapLabel(app.pages["entry"].body, textvariable=app.status, style="Muted.TLabel").pack(fill="x", pady=(4, 0))
    app.chrome = WindowChrome(app, header)
    app.select_page("entry")
    root.bind("<MouseWheel>", app.scroll_page, add="+")
    root.bind("<<AppearanceChanged>>", app.refresh_pages, add="+")
    area = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0)
    width = min(900, area.right - area.left - 40)
    height = min(760, area.bottom - area.top - 50)
    app.shell_bands = (header, nav)
    root.minsize(min(640, width), min(460, height))
    root.geometry(f"{width}x{height}+{area.left + max(12, (area.right-area.left-width)//2)}+{area.top + max(12, (area.bottom-area.top-height)//2)}")
    app.appearance.repaint()


def build_entry(app, parent):
    app.form_title = tk.StringVar(value="Log your day")
    ttk.Label(parent, textvariable=app.form_title, style="Title.TLabel").pack(anchor="w", pady=(0, 4))
    WrapLabel(parent, text="Log work to FreshBooks.",
              style="Muted.TLabel").pack(fill="x", pady=(0, 8))
    account = card(parent, "Client & work")
    field_label(account, "Business")
    app.business_combo = ttk.Combobox(account, state="readonly", width=20)
    app.business_combo.pack(fill="x", pady=(0, 8))
    app.business_combo.bind("<<ComboboxSelected>>", lambda event: app.load_catalog())
    field_label(account, "Client")
    app.client_combo = ttk.Combobox(account, state="readonly", width=20)
    app.client_combo.pack(fill="x", pady=(0, 8))
    app.client_combo.bind("<<ComboboxSelected>>", lambda event: app.filter_projects())
    pair = FieldPair(account)
    field_label(pair.left, "Project · optional")
    field_label(pair.right, "Service · optional")
    app.project_combo = ttk.Combobox(pair.left, state="readonly", width=14)
    app.project_combo.pack(fill="x")
    app.project_combo.bind("<<ComboboxSelected>>", lambda event: app.filter_services())
    app.service_combo = ttk.Combobox(pair.right, state="readonly", width=14)
    app.service_combo.pack(fill="x")
    time_card = card(parent, "Time & notes")
    pair = FieldPair(time_card)
    field_label(pair.left, "Date")
    field_label(pair.right, "Hours · H:MM or decimal")
    app.day, app.hours = tk.StringVar(value=date.today().isoformat()), tk.StringVar(value="8:00")
    row = ttk.Frame(pair.left, style="CardBody.TFrame")
    row.pack(fill="x")
    row.columnconfigure(0, weight=1)
    app.date_entry = ttk.Entry(row, textvariable=app.day, width=12)
    app.date_entry.grid(row=0, column=0, sticky="ew")
    app.calendar_button = CalendarIcon(row, app.open_calendar)
    app.buttons.append(app.calendar_button)
    app.calendar_button.grid(row=0, column=1, padx=(7, 0))
    app.date_entry.bind("<Alt-Down>", lambda event: app.open_calendar())
    app.hours_entry = ttk.Entry(pair.right, textvariable=app.hours, width=10)
    app.hours_entry.pack(fill="x")
    field_label(time_card, "What did you work on?")
    app.note = note_field(time_card, height=3)
    if app.demo:
        app.note.insert("1.0", "Video editing, thumbnails and production notes")
    app.edit_bar = ttk.Frame(time_card, style="CardBody.TFrame")
    app.edit_caption = tk.StringVar()
    ttk.Label(app.edit_bar, textvariable=app.edit_caption, style="CardMuted.TLabel").pack(side="left")
    app.button(app.edit_bar, "Cancel edit", app.cancel_edit).pack(side="right")
    app.footer = ttk.Frame(time_card, style="CardBody.TFrame")
    app.footer.pack(fill="x", pady=(8, 0))
    app.billable = tk.BooleanVar(value=True)
    app.billable_check = ttk.Checkbutton(app.footer, text="Billable", variable=app.billable)
    app.billable_check.pack(side="left")
    app.save_button = app.button(app.footer, "Preview entry" if app.demo else "Log time  ✓", app.submit, True)
    app.save_button.pack(side="right")
    tools = ttk.Frame(parent)
    tools.pack(fill="x", pady=(0, 4))
    app.button(tools, "Reload clients & projects", app.load_profile).pack(side="left")
    app.button(tools, "Check pending save", app.check_pending).pack(side="left", padx=8)
    app.form_controls = [app.business_combo, app.client_combo, app.project_combo, app.service_combo,
                         app.date_entry, app.hours_entry, app.note, app.billable_check]


class SettingsPanel(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app = app
        ttk.Label(self, text="Settings", style="Title.TLabel").pack(anchor="w", pady=(0, 4))
        WrapLabel(self, text="Appearance, reminders and your FreshBooks connection.",
                  style="Muted.TLabel").pack(fill="x", pady=(0, 8))
        appearance = card(self, "Appearance", "Applies immediately to every page.")
        self.theme_value = tk.StringVar(value={"system": "Use Windows setting", "light": "Light", "dark": "Dark"}.get(app.prefs.data["theme"], "Use Windows setting"))
        self.theme_choice = ttk.Combobox(appearance, textvariable=self.theme_value,
                                        values=("Use Windows setting", "Light", "Dark"), state="readonly", width=24)
        self.theme_choice.pack(anchor="w")
        self.theme_choice.bind("<<ComboboxSelected>>", self.change_theme)
        general = card(self, "Reminders & window", "Reminders use this computer's local time. Save settings to apply the options below.")
        self.reminders = tk.BooleanVar(value=app.prefs.data["reminders"])
        self.weekdays = tk.BooleanVar(value=app.prefs.data["weekdays_only"])
        self.startup = tk.BooleanVar(value=startup_enabled() if not app.demo else False)
        self.close_to_tray = tk.BooleanVar(value=app.prefs.data.get("close_to_tray", True))
        self.docked_mode = tk.BooleanVar(value=app.prefs.data.get("docked_mode", False))
        self.always_on_top = tk.BooleanVar(value=app.prefs.data["always_on_top"])
        row = ttk.Frame(general, style="CardBody.TFrame")
        row.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(row, text="Daily reminder at", variable=self.reminders).pack(side="left")
        app.reminder_time = ReminderTime(row, app.prefs.data["time"])
        app.reminder_time.pack(side="left", padx=12)
        ttk.Checkbutton(general, text="Weekdays only", variable=self.weekdays).pack(anchor="w")
        ttk.Checkbutton(general, text="Start when I sign in to Windows", variable=self.startup,
                        state="disabled" if app.demo else "normal").pack(anchor="w")
        ttk.Checkbutton(general, text="Always on top", variable=self.always_on_top).pack(anchor="w")
        ttk.Checkbutton(general, text="Docked mode - taskbar panel", variable=self.docked_mode).pack(anchor="w")
        ttk.Checkbutton(general, text="Close button hides to tray", variable=self.close_to_tray).pack(anchor="w")
        buttons = ttk.Frame(general, style="CardBody.TFrame")
        buttons.pack(fill="x", pady=(8, 0))
        self.save_button = app.button(buttons, "Save settings", self.save, True)
        self.save_button.pack(side="left")
        app.button(buttons, "Test notification", lambda: app.tray.notify()).pack(side="left", padx=8)
        connection = card(self, "FreshBooks connection")
        WrapLabel(connection, textvariable=app.connection_text, style="CardMuted.TLabel").pack(fill="x", pady=(0, 5))
        self.connection_button = app.button(connection, "Show connection setup", self.toggle_connection)
        self.connection_button.pack(anchor="w")
        self.connection_details = ttk.Frame(connection, style="CardBody.TFrame")
        self.connection_expanded = not app.api.connected
        if self.connection_expanded:
            self.connection_details.pack(fill="x", pady=(10, 0))
            self.connection_button.configure(text="Hide connection setup")
        connection = self.connection_details
        WrapLabel(connection, text="1. Enter your developer app's Client ID, secret and registered HTTPS redirect URI.\n"
                  "2. Open browser sign-in and approve access. The localhost error page is expected.\n"
                  "3. Copy that page's complete address into Return URL, then finish within five minutes.",
                  style="CardMuted.TLabel").pack(fill="x", pady=(0, 8))
        credentials = app.vault.get("credentials") or {}
        self.client_id = tk.StringVar(value=credentials.get("client_id", ""))
        self.secret = tk.StringVar()
        self.redirect = tk.StringVar(value=credentials.get("redirect_uri", DEFAULT_REDIRECT))
        self.returned = tk.StringVar()
        for title, variable, mask in [("Client ID", self.client_id, False), ("Client secret · blank keeps the saved secret", self.secret, True),
                                       ("Registered redirect URI", self.redirect, False), ("Return URL · complete address from the browser", self.returned, True)]:
            field_label(connection, title)
            ttk.Entry(connection, textvariable=variable, width=20, show="•" if mask else "").pack(fill="x", pady=(0, 8))
        buttons = ttk.Frame(connection, style="CardBody.TFrame")
        buttons.pack(fill="x", pady=(3, 8))
        app.button(buttons, "Open browser sign-in", self.begin).pack(side="left")
        app.button(buttons, "Finish connection", self.finish, True).pack(side="left", padx=8)
        buttons = ttk.Frame(connection, style="CardBody.TFrame")
        buttons.pack(fill="x", pady=(5, 0))
        app.button(buttons, "Disconnect", self.disconnect).pack(side="left")
        app.button(buttons, "Release pending save…", self.release).pack(side="left", padx=8)

    def toggle_connection(self):
        self.show_connection(not self.connection_expanded)

    def show_connection(self, expanded):
        self.connection_expanded = expanded
        if expanded:
            self.connection_details.pack(fill="x", pady=(10, 0))
        else:
            self.connection_details.pack_forget()
        self.connection_button.configure(text="Hide connection setup" if expanded else "Show connection setup")
        self.app.pages["settings"].sync()

    def change_theme(self, event=None):
        mode = {"Use Windows setting": "system", "Light": "light", "Dark": "dark"}[self.theme_value.get()]
        try:
            self.app.prefs.save(theme=mode)
            self.app.appearance.apply(mode)
        except OSError:
            messagebox.showerror("Appearance", "Could not save the appearance setting.", parent=self.app.root)

    def save(self):
        app = self.app
        try:
            scheduled = app.reminder_time.value()
        except ValueError as exc:
            messagebox.showerror("Reminder time", str(exc), parent=app.root)
            return
        try:
            if not app.demo:
                set_startup(self.startup.get(), app.launcher)
            app.prefs.save(reminders=self.reminders.get(), time=scheduled, weekdays_only=self.weekdays.get(), always_on_top=self.always_on_top.get(), docked_mode=self.docked_mode.get(), close_to_tray=self.close_to_tray.get())
            app.docking.apply()
            app.apply_topmost()
            app.status.set("Settings saved. Reminder is scheduled in local time.")
        except OSError:
            messagebox.showerror("Settings", "Windows could not save settings or startup registration.", parent=app.root)

    def begin(self):
        app = self.app
        try:
            if app.demo:
                raise ValueError("Close preview and run FreshTray normally to connect.")
            saved = app.vault.get("credentials") or {}
            secret = self.secret.get() or (saved.get("client_secret", "") if saved.get("client_id") == self.client_id.get().strip() else "")
            app.attempt = OAuthAttempt({"client_id": self.client_id.get().strip(), "client_secret": secret,
                                        "redirect_uri": self.redirect.get().strip()})
            self.returned.set("")
            webbrowser.open(app.attempt.url())
            app.status.set("Browser sign-in started. Paste the full return URL into Settings.")
        except ValueError as exc:
            messagebox.showerror("FreshBooks setup", str(exc), parent=app.root)

    def finish(self):
        app = self.app
        if not app.attempt:
            messagebox.showerror("FreshBooks setup", "Open browser sign-in from this page first.", parent=app.root)
            return
        attempt, returned = app.attempt, self.returned.get()
        def connected(_):
            self.returned.set("")
            self.secret.set("")
            app.attempt = None
            self.show_connection(False)
            app.load_profile()
        app.run(lambda: app.api.connect(attempt, returned), connected, "Completing the secure FreshBooks connection…")

    def disconnect(self):
        app = self.app
        if not app.confirm_replace_form():
            return
        if app.history_window and app.history_window.winfo_exists() and not app.history_window.editor.confirm_discard():
            return
        def disconnected(_):
            app.cancel_edit(confirm=False)
            if app.history_window and app.history_window.winfo_exists():
                app.history_window.destroy()
                app.history_window = None
            app.profile_data, app.businesses, app.clients, app.projects, app.services = {}, [], [], [], []
            for combo in (app.business_combo, app.client_combo, app.project_combo, app.service_combo):
                combo.set("")
                combo["values"] = []
            app.connection_text.set("FreshBooks is disconnected")
            app.status.set("Disconnected. Local credentials removed after revocation.")
            self.client_id.set("")
            self.secret.set("")
            self.show_connection(True)
        app.run(app.api.disconnect, disconnected, "Revoking the FreshBooks connection…")

    def release(self):
        app = self.app
        pending = app.vault.get("pending")
        if not pending:
            messagebox.showinfo("Pending save", "No pending submission.", parent=app.root)
            return
        entry = pending["payload"]["time_entry"]
        if messagebox.askyesno("Release pending save", f'Pending: {entry["duration"]/3600:g} hours, {entry["started_at"]}\n\n'
            'Have you checked FreshBooks yourself? Releasing removes only the local guard. Submitting again could create a duplicate.', parent=app.root):
            app.vault.update(pending=None)
            app.status.set("Pending guard released. Review the form before submitting again.")

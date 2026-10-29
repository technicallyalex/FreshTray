"""Monthly FreshBooks history, day details and entry edit/add actions."""
import calendar
import ctypes
from ctypes import wintypes
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox

from .scrollbars import SlimScrollbar
from .monthly_editor import MonthlyEditor
from .components import card, WrapLabel, note_field, CalendarGrid
from .history_model import month_after, entry_date, day_totals, format_duration, edit_restriction


class MonthlyView(ttk.Frame):
    def __init__(self, app, business, profile):
        super().__init__(app.history_host)
        self.app, self.business, self.profile = app, dict(business), dict(profile)
        self.month, self.selected_day = date.today().replace(day=1), date.today()
        self.entries, self.rows, self.day_buttons, self.totals = [], {}, {}, {}
        self.data_loaded, self.controls = False, []
        body = self
        ttk.Label(body, text="Monthly hours", style="Title.TLabel").pack(anchor="w", pady=(0, 4))
        name = " ".join(filter(None, [profile.get("first_name"), profile.get("last_name")])) or "Connected user"
        WrapLabel(body, text=f'{business["name"]}  ·  {name}' + ("  ·  Offline preview" if app.demo else ""),
                  style="Muted.TLabel").pack(fill="x", pady=(0, 8))
        calendar_card = card(body)
        header = ttk.Frame(calendar_card, style="CardBody.TFrame")
        header.pack(fill="x", pady=(0, 7))
        self.toolbar = header
        self.control(header, "‹", lambda: self.shift_month(-1), width=3).pack(side="left")
        self.control(header, "›", lambda: self.shift_month(1), width=3).pack(side="left", padx=(5, 12))
        self.month_choice = ttk.Combobox(header, state="readonly", values=list(calendar.month_name)[1:], width=12)
        self.month_choice.pack(side="left")
        self.month_choice.bind("<<ComboboxSelected>>", lambda event: self.jump_month())
        self.year_value = tk.StringVar(value=str(self.month.year))
        self.year_choice = ttk.Spinbox(header, textvariable=self.year_value, from_=1, to=9998, width=5, command=self.jump_month)
        self.year_choice.pack(side="left", padx=7)
        self.year_choice.bind("<Return>", lambda event: self.jump_month())
        self.controls.extend([self.month_choice, self.year_choice])
        self.control(header, "Go", self.jump_month, width=4).pack(side="left")
        tools = ttk.Frame(calendar_card, style="CardBody.TFrame")
        tools.pack(fill="x", pady=(0, 8))
        self.control(tools, "Today", self.today).pack(side="left")
        self.control(tools, "Refresh", self.refresh).pack(side="left", padx=8)
        self.total_text = tk.StringVar(value="Monthly total: —")
        ttk.Label(tools, textvariable=self.total_text, style="Section.TLabel").pack(side="right")
        self.month_grid = CalendarGrid(calendar_card)
        self.month_grid.pack(fill="x")
        ttk.Label(calendar_card, text="• Time logged", style="CalendarLegend.TLabel").pack(anchor="w", pady=(5, 0))
        details = card(body)
        self.day_text = tk.StringVar()
        WrapLabel(details, textvariable=self.day_text, style="Section.TLabel").pack(fill="x", pady=(0, 7))
        table = ttk.Frame(details, style="CardBody.TFrame")
        table.pack(fill="x")
        table.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=("client", "hours", "project", "service", "note", "status"),
                                 show="headings", height=3, selectmode="browse")
        for key, title, width in [("client", "Client", 185), ("hours", "Hours", 85), ("project", "Project", 140),
                                   ("service", "Service", 130), ("note", "Note", 240), ("status", "Status", 110)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=65, stretch=key in ("client", "note"), anchor="e" if key == "hours" else "w")
        self.preferred_table_width = sum(self.tree.column(c, "width") for c in self.tree["columns"])
        self.tree.grid(row=0, column=0, sticky="ew")
        yscroll = SlimScrollbar(table, surface="panel", orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = SlimScrollbar(table, surface="panel", orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.update_actions())
        self.tree.bind("<Double-1>", self.double_click_entry)
        self.tree.bind("<Return>", lambda event: self.edit_selected())
        self.selection_summary = tk.StringVar(value="Select an entry to read its full details.")
        WrapLabel(details, textvariable=self.selection_summary, style="CardMuted.TLabel").pack(fill="x", pady=(8, 4))
        self.note_preview = note_field(details, height=2, readonly=True)
        actions = ttk.Frame(details, style="CardBody.TFrame")
        actions.pack(fill="x", pady=(0, 8), before=table)
        self.add_button = ttk.Button(actions, text="Add entry for this day", command=self.add_entry, style="Accent.TButton")
        self.add_button.pack(side="left")
        self.edit_button = ttk.Button(actions, text="Edit selected entry", command=self.edit_selected)
        self.edit_button.pack(side="left", padx=8)
        self.action_hint = tk.StringVar()
        WrapLabel(details, textvariable=self.action_hint, style="CardMuted.TLabel").pack(fill="x", before=table, pady=(0, 5))
        editor_card = card(body)
        self.editor = MonthlyEditor(self, editor_card)
        self.editor.pack(fill="x")
        self.status = tk.StringVar(value="Loading month…")
        WrapLabel(body, textvariable=self.status, style="Muted.TLabel").pack(fill="x", pady=(0, 8))
        self.month_choice.current(self.month.month - 1)
        self.render_grid()
        self.show_day()

    def fit_page_width(self):
        if not self.winfo_exists():
            return
        page = self.app.pages["history"]
        page.min_width = max(740, self.toolbar.winfo_reqwidth() + 80, self.month_grid.winfo_reqwidth() + 80)
        page.sync()


    def control(self, parent, text, command, **options):
        button = ttk.Button(parent, text=text, command=command, **options)
        self.controls.append(button)
        return button

    def set_context(self, business, profile):
        self.business, self.profile = dict(business), dict(profile)
        # Recreate on a business/account change so captions never retain stale context.
        self.entries, self.totals, self.rows = [], {}, {}
        self.data_loaded = False

    def set_busy(self, value):
        for control in self.controls:
            control.configure(state="disabled" if value else ("readonly" if control is self.month_choice else "normal"))
        for button in self.day_buttons.values():
            button.configure(state="disabled" if value else "normal")
        self.update_actions()
        self.editor.update_enabled()

    def refresh(self, saved_status=None, selected_id=None):
        if self.app.busy or not self.winfo_exists():
            return
        self.entries, self.totals = [], {}
        self.data_loaded = False
        self.status.set("Loading logged hours from FreshBooks…" if not self.app.demo else "Loading offline sample entries…")
        self.render_grid()
        self.show_day()
        month = self.month
        business_id, identity = self.business["id"], self.profile["id"]

        def loaded(entries):
            if not self.winfo_exists():
                return
            self.entries, self.totals, self.data_loaded = entries, day_totals(entries), True
            self.render_grid()
            self.show_day()
            if str(selected_id) in self.rows:
                self.tree.selection_set(str(selected_id))
                self.update_actions()
            self.status.set(f'{len(entries)} entries loaded. Select a day to view, add or edit time.')
            self.app.status.set(saved_status or "Monthly hours loaded.")
            self.set_busy(False)

        def failed(text):
            if self.winfo_exists():
                self.status.set(text + " Use Refresh to try again.")
                self.set_busy(False)

        self.app.run(lambda: self.app.api.entries_for_month(business_id, month, identity), loaded,
                     "Loading monthly hours…", on_error=failed)

    def change_month(self, month, selected=None):
        if self.app.busy:
            return
        if not self.editor.confirm_discard():
            self.month_choice.current(self.month.month - 1)
            self.year_value.set(str(self.month.year))
            return
        self.month = month.replace(day=1)
        self.selected_day = selected or self.month.replace(day=min(self.selected_day.day, calendar.monthrange(month.year, month.month)[1]))
        self.month_choice.current(self.month.month - 1)
        self.year_value.set(str(self.month.year))
        self.editor.reset_for_day(self.selected_day)
        self.refresh()

    def shift_month(self, offset):
        if self.app.busy:
            return
        try:
            month = month_after(self.month, offset)
            if month.year > 9998:
                return
            self.change_month(month)
        except ValueError:
            return

    def jump_month(self):
        if self.app.busy:
            return
        try:
            year = int(self.year_value.get())
            if not 1 <= year <= 9998:
                raise ValueError()
            self.change_month(date(year, self.month_choice.current() + 1, 1))
        except ValueError:
            messagebox.showerror("Choose a month", "Enter a valid year and choose a month.", parent=self.app.root)

    def today(self):
        self.change_month(date.today().replace(day=1), date.today())

    def render_grid(self):
        for child in self.month_grid.winfo_children():
            child.destroy()
        for row in range(7):
            self.month_grid.rowconfigure(row, weight=0)
        self.day_buttons = {}
        entry_days = {entry_date(entry) for entry in self.entries} if self.data_loaded else set()
        for column, title in enumerate(("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Total")):
            ttk.Label(self.month_grid, text=title, anchor="center", style="WeekTotal.TLabel").grid(
                row=0, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))
            self.month_grid.columnconfigure(column, weight=1, uniform="monthday")
        self.week_totals = []
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(self.month.year, self.month.month)
        for row, week in enumerate(weeks, 1):
            self.month_grid.rowconfigure(row, weight=0, minsize=self.app.appearance.line_height * 2 + 12)
            weekly = 0
            valid_days = [d for d in week if d]
            for column, number in enumerate(week):
                if not number:
                    ttk.Label(self.month_grid, text="", style="OutsideMonth.TLabel").grid(row=row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))
                    continue
                day = self.month.replace(day=number)
                total = self.totals.get(day, 0)
                weekly += total
                text = f'{number}\n{format_duration(total) if total else ""}' if self.data_loaded else f"{number}\n—"
                if day in entry_days:
                    text = text.replace(str(number), f"{number}  •", 1)
                button = ttk.Button(self.month_grid, text=text, command=lambda chosen=day: self.select_day(chosen),
                                    style="SelectedMonthDay.TButton" if day == self.selected_day else "MonthDay.TButton")
                button.grid(row=row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))
                self.day_buttons[day] = button
            self.week_totals.append(weekly)
            label = f'{valid_days[0]}–{valid_days[-1]}\n{format_duration(weekly) if self.data_loaded else "—"}'
            ttk.Label(self.month_grid, text=label, anchor="center", style="WeekTotal.TLabel").grid(row=row, column=7, sticky="nsew", padx=(0, 1), pady=(0, 1))
        self.total_text.set("Monthly total: " + (format_duration(sum(self.totals.values())) if self.data_loaded else "—"))
        self.after_idle(self.fit_page_width)

    def select_day(self, day):
        if self.app.busy:
            return
        changed = day != self.selected_day
        if changed:
            if not self.editor.confirm_discard():
                return
            self.selected_day = day
            self.editor.reset_for_day(day)
        self.render_grid()
        self.show_day()
        if changed:
            self.reveal_editor()

    def names(self):
        clients = {str(c.get("id", c.get("userid"))): self.app.label_client(c) for c in self.app.clients}
        projects = {str(p["id"]): p["title"] for p in self.app.projects}
        services = {str(s["id"]): s["name"] for s in self.app.services}
        for project in self.app.projects:
            services.update({str(s["id"]): s["name"] for s in project.get("services", [])})
        return clients, projects, services

    def show_day(self):
        self.day_text.set(self.selected_day.strftime("%A, %B %d, %Y") + "  ·  " +
                          (format_duration(self.totals.get(self.selected_day, 0)) if self.data_loaded else "—"))
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        clients, projects, services = self.names()
        for entry in self.entries:
            if entry_date(entry) != self.selected_day:
                continue
            key = str(entry["id"])
            self.rows[key] = entry
            client = clients.get(str(entry.get("client_id")), "Unavailable client" if entry.get("client_id") else "Internal")
            project = projects.get(str(entry.get("project_id")), "Unavailable project" if entry.get("project_id") else "—")
            service = services.get(str(entry.get("service_id")), "Unavailable service" if entry.get("service_id") else "—")
            self.tree.insert("", "end", iid=key, values=(client, format_duration(entry.get("duration")), project, service,
                (entry.get("note") or "").replace("\n", " "), "Billed" if entry.get("billed") else ("Billable" if entry.get("billable") else "Non-billable")))
        if self.rows:
            self.tree.selection_set(next(iter(self.rows)))
        if self.data_loaded:
            self.status.set("Select an entry to edit, or add another for this day." if self.rows else
                            ("No entries for this day. Fill in the form below to log time." if self.selected_day <= date.today() else
                             "Future days are shown for reference. Entries can be added up to today."))
        self.update_actions()

    def update_actions(self):
        ready = self.data_loaded and not self.app.busy
        self.add_button.configure(state="normal" if ready and self.selected_day <= date.today() else "disabled")
        selection = self.tree.selection()
        entry = self.rows.get(selection[0]) if selection else None
        self.edit_button.configure(state="normal" if ready and entry and not edit_restriction(entry) else "disabled")
        if entry:
            clients, projects, services = self.names()
            self.selection_summary.set(" · ".join(filter(None, [
                clients.get(str(entry.get("client_id")), "Internal" if not entry.get("client_id") else "Unavailable client"),
                projects.get(str(entry.get("project_id"))), services.get(str(entry.get("service_id"))),
                format_duration(entry.get("duration")) + " hours"])))
            note = entry.get("note") or "No note for this entry."
        else:
            self.selection_summary.set("Select an entry to read its full details.")
            note = ""
        if self.note_preview.get("1.0", "end-1c") != note:
            self.note_preview.configure(state="normal")
            self.note_preview.delete("1.0", "end")
            self.note_preview.insert("1.0", note)
            self.note_preview.configure(state="disabled")
        self.action_hint.set(edit_restriction(entry) if entry and edit_restriction(entry) else
                             ("Already billed. You can edit this entry; its billed status is retained." if entry and entry.get("billed") else
                              "Edit opens the selected entry in the form below." if entry else "Use the form below to add time for this day."))
        if ready and entry and edit_restriction(entry):
            self.status.set(edit_restriction(entry))

    def add_entry(self):
        if self.app.busy or not self.data_loaded or self.selected_day > date.today():
            return
        if self.editor.confirm_discard():
            self.editor.reset_for_day(self.selected_day)
            self.reveal_editor()

    def reveal_editor(self):
        self.app.pages["history"].reveal(self.editor)
        self.editor.note.focus_set()

    def saved_entry(self, entry, text):
        self.selected_day = entry_date(entry)
        self.month = self.selected_day.replace(day=1)
        self.month_choice.current(self.month.month - 1)
        self.year_value.set(str(self.month.year))
        self.editor.reset_for_day(self.selected_day)
        self.refresh(saved_status=text, selected_id=entry["id"])

    def double_click_entry(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.edit_selected()
        return "break"

    def edit_selected(self):
        if self.app.busy or not self.data_loaded:
            return
        selection = self.tree.selection()
        entry = self.rows.get(selection[0]) if selection else None
        if not entry:
            return
        restriction = edit_restriction(entry)
        if restriction:
            self.status.set(restriction)
            return
        if not self.editor.confirm_discard():
            return
        bid, ident = self.business["id"], entry["id"]
        def loaded(fresh):
            if str(fresh.get("id")) != str(ident):
                raise ValueError("FreshBooks returned a different entry. Refresh the calendar and try again.")
            self.editor.load_entry(fresh)
            self.reveal_editor()
            self.status.set("Edit the fields below, then choose Save changes.")
        self.app.run(lambda: self.app.api.get_entry(bid, ident), loaded, "Loading the selected entry…",
                     on_error=self.editor.notice.set)

"""Exercise the real monthly editor with an isolated editable offline backend."""
import argparse
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

import _paths
from freshtray.api import ApiError
from freshtray.demo import Demo
from freshtray.storage import Preferences, Vault
from freshtray.ui import App
from freshtray.history_model import month_after, entry_date, day_totals


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scaling',type=float)
    args=parser.parse_args()
    root=tk.Tk();root.withdraw();app=None
    if args.scaling:root.tk.call('tk','scaling',args.scaling)
    with tempfile.TemporaryDirectory() as directory:
        folder=Path(directory);prefs=Preferences(folder/'settings.json')
        prefs.save(reminders=False,always_on_top=True)
        try:
            app=App(root,Demo(),Vault(folder/'vault.dpapi'),prefs,Path(__file__).resolve().parents[1]/'src/assets',Path(__file__),True)
            def settle():
                deadline=time.monotonic()+8
                while app.busy and time.monotonic()<deadline:
                    root.update();time.sleep(.01)
                root.update();assert not app.busy
            settle();app.open_history();settle()
            h=app.history_window;e=h.editor
            assert h.data_loaded and h.entries and app.active_page=='history'
            assert h.winfo_toplevel()==root and root.attributes('-topmost')
            assert sum(h.week_totals)==sum(h.totals.values())
            original_month=h.month
            h.shift_month(-1);settle();assert h.month==month_after(original_month,-1)
            h.shift_month(1);settle();assert h.month==original_month
            h.year_value.set('2024');h.month_choice.current(1);h.jump_month();settle()
            assert date(2024,2,29) in h.day_buttons and len(h.day_buttons)==29
            h.today();settle()
            first=deepcopy(h.entries[0]);ident=first['id'];selected=entry_date(first)
            h.day_buttons[selected].invoke();root.update()
            assert e.day.get()==selected.isoformat() and e.original is None
            assert e.winfo_ismapped() and str(ident) in h.rows
            # The main Log time draft must never be replaced by calendar edits.
            app.note.delete('1.0','end');app.note.insert('1.0','Separate main-page draft')
            main_draft=app._form_state()
            h.tree.selection_set(str(ident));h.edit_button.invoke();settle()
            assert e.original['id']==ident and app.active_page=='history' and app.editing_entry is None
            assert e.save_button.cget('text')=='Preview changes'
            count=len(app.api.entries)
            e.hours.set('6:30');e.note.delete('1.0','end');e.note.insert('1.0','Edited inline')
            e.save_button.invoke();settle()
            changed=app.api.get_entry(1,ident)
            assert len(app.api.entries)==count and changed['duration']==23400 and changed['note']=='Edited inline'
            assert changed['started_at']==first['started_at']
            assert e.original is None and h.totals==day_totals(h.entries) and not e.dirty()
            # Add another entry in the same view and refresh its row, totals and marker.
            h.add_button.invoke();root.update()
            assert app.active_page=='history' and e.day.get()==selected.isoformat()
            e.hours.set('1:15');e.note.insert('1.0','Additional work')
            e.save_button.invoke();settle()
            assert len(app.api.entries)==count+1 and len(h.rows)==2 and h.totals[selected]==27900
            assert '•' in h.day_buttons[selected].cget('text')
            # Move the exact selected entry, preserving its timestamp's local clock.
            h.tree.selection_set(str(ident));h.edit_button.invoke();settle()
            target=selected+timedelta(days=1);e.day.set(target.isoformat());e.save_button.invoke();settle()
            assert len(app.api.entries)==count+1 and entry_date(app.api.get_entry(1,ident))==target
            assert h.selected_day==target and str(ident) in h.rows and h.totals[selected]==4500
            # Billed entries now open and retain their billed state when edited.
            app.api.entries[ident]['billed']=True;h.refresh();settle()
            h.tree.selection_set(str(ident));root.update()
            assert 'disabled' not in h.edit_button.state() and 'billed' in h.action_hint.get().lower()
            h.edit_button.invoke();settle()
            assert e.original['billed'] and 'Already billed' in e.notice.get()
            e.note.delete('1.0','end');e.note.insert('1.0','Billed entry correction')
            assert 'billed' not in e.payload()['time_entry']
            e.save_button.invoke();settle()
            assert app.api.get_entry(1,ident)['billed'] and app.api.get_entry(1,ident)['note']=='Billed entry correction'
            assert len(app.api.entries)==count+1
            # Double-click must load the clicked row, even with another row selected.
            h.select_day(selected);root.update()
            remaining=next(iter(h.rows));bounds=h.tree.bbox(remaining)
            assert bounds
            h.double_click_entry(SimpleNamespace(y=bounds[1]+2));settle()
            assert str(e.original['id'])==remaining and app.active_page=='history'
            e.reset_for_day(h.selected_day)
            # Concurrency rejection keeps the inline draft and makes no replacement entry.
            h.select_day(target);h.tree.selection_set(str(ident));h.edit_button.invoke();settle()
            app.api.entries[ident]['note']='Changed externally'
            e.note.delete('1.0','end');e.note.insert('1.0','My unsaved change')
            with patch('freshtray.ui.messagebox.showerror'):
                e.save_button.invoke();settle()
            assert 'changed' in e.notice.get().lower() and e.note.get('1.0','end-1c')=='My unsaved change'
            assert len(app.api.entries)==count+1 and app.api.get_entry(1,ident)['note']=='Changed externally'
            state=e.state();old_day=h.selected_day
            with patch('freshtray.monthly_editor.messagebox.askyesno',return_value=False):
                h.select_day(selected);assert h.selected_day==old_day and e.state()==state
                old_month=h.month;h.month_choice.current((h.month.month)%12);h.jump_month()
                assert h.month==old_month and h.month_choice.current()==old_month.month-1
                h.add_button.invoke();assert e.state()==state
            # Failed refresh disables all writes and retains the monthly draft for retry.
            with patch.object(app.api,'entries_for_month',side_effect=ApiError('Offline')),patch('freshtray.ui.messagebox.showerror'):
                h.refresh();settle()
            assert not h.data_loaded and not h.entries and e.state()==state
            assert 'disabled' in e.save_button.state() and 'disabled' in h.edit_button.state()
            assert 'Offline' in h.status.get()
            h.refresh();settle();assert h.data_loaded and e.state()==state
            e.reset_for_day(h.selected_day)
            # Archived IDs and a service assigned only to the project are retained exactly.
            historical=deepcopy(changed);historical.update(client_id=900,project_id=901,service_id=902)
            e.load_entry(historical)
            payload=e.payload()['time_entry']
            assert (payload['client_id'],payload['project_id'],payload['service_id'])==(900,901,902)
            e.reset_for_day(h.selected_day)
            project_only=deepcopy(changed);project_only.update(service_id=777)
            e.projects[0]['services'].append({'id':777,'name':'Project-only service'})
            e.load_entry(project_only);assert e.payload()['time_entry']['service_id']==777
            assert e.service_combo.get()=='Project-only service'
            e.reset_for_day(h.selected_day)
            # Move across a month boundary and stay in the new month after saving.
            h.tree.selection_set(str(ident));h.edit_button.invoke();settle()
            previous_month=month_after(h.month,-1)
            e.day.set(previous_month.isoformat());e.save_button.invoke();settle()
            assert h.month==previous_month and h.selected_day==previous_month
            assert str(ident) in h.rows and app.api.get_entry(1,ident)['billed']
            # Confirming an interrupted edit clears only its matching draft and follows its saved date.
            h.tree.selection_set(str(ident));h.edit_button.invoke();settle()
            e.day.set(target.isoformat());e.note.delete('1.0','end');e.note.insert('1.0','Recovered edit')
            recovered=dict(app.api.get_entry(1,ident),**e.payload()['time_entry'])
            app.api.entries[ident]=deepcopy(recovered)
            app.vault.update(last_success={'business_id':1,'id':ident,'payload':e.payload()})
            with patch.object(app.api,'check_pending',return_value=recovered):
                app.check_pending();settle()
            assert e.original is None and not e.dirty() and h.selected_day==target
            assert h.month==target.replace(day=1) and str(ident) in h.rows
            # A confirmed old save must not erase a newer, different monthly draft.
            e.note.insert('1.0','A new draft after recovery');new_draft=e.state()
            with patch.object(app.api,'check_pending',return_value=recovered):
                app.check_pending();settle()
            assert e.state()==new_draft
            e.reset_for_day(h.selected_day)
            # Future days cannot submit; invalid hours cannot call the backend.
            h.change_month((date.today()+timedelta(days=1)).replace(day=1),date.today()+timedelta(days=1));settle()
            assert 'disabled' in e.save_button.state() and 'disabled' in h.add_button.state()
            h.today();settle();e.hours.set('0')
            with patch.object(app.api,'submit') as submit,patch('freshtray.monthly_editor.messagebox.showerror'):
                e.submit();assert not submit.called
            e.reset_for_day(h.selected_day)
            assert app._form_state()==main_draft, 'Monthly workflows changed the main-page draft'
            # Deleted/running/internal entries and another user's entries are still protected.
            for field in ({'active':False},{'is_logged':False},{'internal':True},{'identity_id':99}):
                bad=deepcopy(changed);bad.update(field)
                try:e.load_entry(bad)
                except ValueError:pass
                else:raise AssertionError('Restricted entry opened for editing')
            # Themes, long previews and small windows preserve readable, reachable controls.
            h.change_month(target.replace(day=1),target);settle()
            note='Full note remains readable. '*35;app.api.entries[ident]['note']=note
            h.refresh();settle();h.tree.selection_set(str(ident));root.update()
            assert h.note_preview.get('1.0','end-1c')==note
            for mode in ('dark','light'):
                app.appearance.apply(mode);root.update()
                assert e.note.cget('background')==app.appearance.palette['field']
            for width,height in ((640,460),(900,700),(1180,900)):
                root.geometry(f'{width}x{height}');root.update()
                for button in h.day_buttons.values():assert button.winfo_height()>=button.winfo_reqheight()
                app.pages['history'].reveal(e);root.update()
                if e.winfo_height()>app.pages['history'].viewport.winfo_height():
                    app.pages['history'].viewport.yview_moveto(1);root.update()
                assert e.save_button.winfo_rooty()+e.save_button.winfo_height()<=app.pages['history'].viewport.winfo_rooty()+app.pages['history'].viewport.winfo_height()+1
            print('PASS: inline monthly add/edit, billed status retained, double-click, same-ID saves, moved dates/months, totals/markers, independent drafts, discard guards, stale conflicts, load failures, archived/project-only IDs, validation, themes and small-window reachability.')
        finally:
            if app:app.tray.close();app.executor.shutdown(wait=True)
            root.destroy()

if __name__=='__main__':main()


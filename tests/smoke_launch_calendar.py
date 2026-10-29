"""Offline checks for startup fit, name-only choices and monthly entry markers."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

project=Path(__file__).resolve().parents[1]
import _paths  # Make src imports independent of the working directory.
from freshtray.ui import App
from freshtray.demo import Demo
from freshtray.storage import Vault, Preferences
from freshtray.sizing import LaunchFit, fitted_size, work_area, frame_size
from freshtray.history_model import entry_date, day_totals

parser=argparse.ArgumentParser()
parser.add_argument('--scaling',type=float,default=4/3)
args=parser.parse_args()

class Backend(Demo):
    reads=0
    def entries_for_month(self,*args):
        self.reads+=1
        return super().entries_for_month(*args)

assert fitted_size((1100,900),(1000,800),(16,40))==(960,736)
assert fitted_size((800,600),(1920,1080),(16,40))==(800,600)
root=tk.Tk();root.withdraw();root.tk.call('tk','scaling',args.scaling)
app=None
with tempfile.TemporaryDirectory() as directory:
    folder=Path(directory);prefs=Preferences(folder/'settings.json')
    prefs.save(reminders=False,theme='light',layout_revision=1,window_size=[640,460])
    try:
        backend=Backend()
        app=App(root,backend,Vault(folder/'vault.dpapi'),prefs,project/'src/assets',Path(__file__),True)
        def settle():
            deadline=time.monotonic()+8
            while app.busy and time.monotonic()<deadline:
                root.update();time.sleep(.01)
            root.update();assert not app.busy
        settle()
        assert root.state()=='withdrawn', 'Background launch must stay hidden'
        app.show();root.update()
        assert not app.launch_fit.pending and app.active_page=='entry'
        assert backend.reads==0, 'Measuring the calendar must not fetch entries'
        left,top,right,bottom=work_area(root);chrome=frame_size(root)
        width,height=root.winfo_width(),root.winfo_height()
        assert width+chrome[0]<=right-left and height+chrome[1]<=bottom-top
        assert (width,height)!=(640,460), 'Undersized saved window defeated launch fit'
        max_height=bottom-top-chrome[1]-24
        for name,page in app.pages.items():
            app.select_page(name);root.update()
            required=page.body.winfo_reqheight()
            if root.winfo_height()<max_height-2:
                assert required<=page.viewport.winfo_height(), (name,required,page.viewport.winfo_height())
        assert app.business_combo.get()=='Preview business'
        assert app.client_combo.get()=='Example Studio'
        assert tuple(app.project_combo['values'])==('No project','Video production')
        assert tuple(app.service_combo['values'])==('No service','Editing','Thumbnail design')
        # Native selected indices keep distinct records distinct even if names match.
        app.clients.append({'id':98765,'organization':'Example Studio'})
        app.client_combo['values']=[app.label_client(c) for c in app.clients]
        app.client_combo.current(1)
        assert app._form_state()[1]==98765
        app.client_combo.current(0)
        assert app._form_state()[1]==1
        assert app.label_client({'id':222,'organization':'Studio · East'})=='Studio · East'
        app.open_history();settle();history=app.history_window
        history_height=root.winfo_height()
        reads=backend.reads
        app.show_entry();root.update()
        assert root.winfo_height()<history_height, 'Log page did not shrink'
        app.open_history();root.update()
        assert backend.reads==reads and not app.busy, 'Tab switch refreshed loaded history'
        assert root.winfo_height()>=history_height-2
        days={entry_date(entry) for entry in history.entries}
        for day,button in history.day_buttons.items():
            assert ('•' in button.cget('text'))==(day in days)
        empty=next(day for day in history.day_buttons if day not in days)
        zero=deepcopy(history.entries[0]);zero.update(id=999999,duration=0,started_at=empty.isoformat()+'T12:00:00')
        assert entry_date(zero)==empty
        history.entries.append(zero);history.totals=day_totals(history.entries)
        history.render_grid();root.update()
        assert '•' in history.day_buttons[empty].cget('text'), 'Zero-hour entries still need a marker'
        for theme in ('dark','light'):
            app.appearance.apply(theme);root.update()
            assert history.month_grid.cget('background')==app.appearance.palette['border']
            for button in history.day_buttons.values():
                assert tuple(map(int,button.grid_info()['padx']))==(0,1)
                assert tuple(map(int,button.grid_info()['pady']))==(0,1)
        # Month reload must remove stale dots and keep fresh ones.
        history.refresh();settle()
        assert '•' not in history.day_buttons[empty].cget('text')
        root.geometry('800x650');root.update();app.settings();root.update()
        assert root.winfo_height()>0
        # On a smaller desktop, cap the window and keep overflow reachable.
        with patch('freshtray.sizing.work_area',return_value=(0,0,1000,800)):
            app.launch_fit=LaunchFit(app);app.launch_fit.ready();root.update()
        assert root.winfo_width()+chrome[0]<=1000 and root.winfo_height()+chrome[1]<=800
        app.select_page('history');root.update()
        page=app.pages['history'];page.viewport.yview_moveto(1);root.update()
        assert page.viewport.yview()[1]==1.0
        assert page.body.winfo_rooty()+page.body.winfo_height()<=page.viewport.winfo_rooty()+page.viewport.winfo_height()+1
        print(f'PASS: launch fit {width}x{height}, background launch, all-page measurement, names/duplicate IDs, zero-hour markers, themed grid, refresh and manual resize (scale {args.scaling}).')
    finally:
        if app:app.tray.close();app.executor.shutdown(wait=True)
        root.destroy()

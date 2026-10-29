from pathlib import Path
import argparse
import sys
import tempfile
import time
import tkinter as tk

project=Path(__file__).resolve().parents[1]
import _paths  # Make src imports independent of the working directory.
from freshtray.ui import App
from freshtray.demo import Demo
from freshtray.storage import Vault, Preferences

parser=argparse.ArgumentParser()
parser.add_argument('--scaling',type=float)
parser.add_argument('--cycles',type=int,default=45)
args=parser.parse_args()
root=tk.Tk()
if args.scaling:root.tk.call('tk','scaling',args.scaling)
root.withdraw()
app=None
with tempfile.TemporaryDirectory() as directory:
    folder=Path(directory)
    prefs=Preferences(folder/'settings.json')
    prefs.save(reminders=False,theme='light')
    try:
        app=App(root,Demo(),Vault(folder/'vault.dpapi'),prefs,project/'src/assets',Path(__file__),True)
        app.show()
        def settle():
            until=time.monotonic()+5
            while app.busy and time.monotonic()<until:
                root.update(); time.sleep(.01)
            root.update(); assert not app.busy
        settle()
        for _ in range(20):
            app.chrome.apply();app.chrome.maximize();root.update()
            app.chrome.maximize();root.update()
            app.chrome.minimize();root.update();app.show();root.update()
        assert len(app.chrome.icons)==3
        assert all(icon.find_all() for icon in app.chrome.icons)
        from unittest.mock import patch
        with patch.object(app,'hide') as hide,patch.object(app,'quit') as quit:
            app.prefs.save(close_to_tray=True);app.close_window();assert hide.called
            app.prefs.save(close_to_tray=False);app.close_window();assert quit.called
        from types import SimpleNamespace
        size=(root.winfo_width(),root.winfo_height())
        draft=app._form_state()
        for page in ('entry','history','settings','entry'):
            app.select_page(page);root.update()
            size=(root.winfo_width(),root.winfo_height())
            app.chrome.drag_start(SimpleNamespace(x_root=200,y_root=200))
            for step in range(100):
                app.chrome.drag(SimpleNamespace(x_root=200+step,y_root=200+step//2))
                if step%10==0:root.update()
            app.chrome.drag_end();root.update()
            assert (root.winfo_width(),root.winfo_height())==size
            assert app.pages[page].body.winfo_ismapped()
        assert app._form_state()==draft
        root.geometry('900x760')
        app.show_entry(); root.update()
        for name,page in app.pages.items():
            if name=='history':continue
            app.select_page(name);root.update()
            if float(root.tk.call('tk','scaling')) < 1.4:
                assert page.body.winfo_reqheight() <= page.viewport.winfo_height(), f'{name} no longer fits at 900x760'
            assert page.body.winfo_ismapped() and page.viewport.winfo_ismapped()
            assert app.settings_window.winfo_toplevel()==root

        app.open_history();settle()
        h=app.history_window;p=app.pages['history']
        if float(root.tk.call('tk','scaling')) < 1.4:
            assert h.add_button.winfo_rooty()+h.add_button.winfo_height() <= p.viewport.winfo_rooty()+p.viewport.winfo_height()
        # Expanding setup must not destroy typed values or leave an empty viewport on collapse.
        app.settings()
        setup=app.settings_window
        setup.client_id.set('offline-test-client')
        setup.show_connection(True)
        root.update()
        assert setup.connection_details.winfo_ismapped()
        app.pages['settings'].viewport.yview_moveto(1)
        setup.show_connection(False)
        root.update()
        assert setup.client_id.get()=='offline-test-client'
        assert not setup.connection_details.winfo_ismapped()
        app.show_entry()
        root.update()

        for i in range(args.cycles):
            width,height=((640,460),(900,760),(1100,1300))[i%3]
            root.geometry(f'{width}x{height}')
            app.settings()
            app.settings_window.theme_value.set('Dark' if i%2==0 else 'Light')
            app.settings_window.change_theme()
            app.open_history()
            app.show_entry()
            root.update();settle()
            page=app.pages['entry']
            assert page.body.winfo_manager()=='place'
            assert app.client_combo.winfo_ismapped(),f'Hidden form at cycle {i}'
            assert page.body.winfo_rooty()<page.viewport.winfo_rooty()+page.viewport.winfo_height()
            assert page.body.winfo_rooty()+page.body.winfo_height()>page.viewport.winfo_rooty()
            assert sum(p.winfo_ismapped() for p in app.pages.values())==1
            assert app.page_host.select()==str(page), 'Visible tab and navigation selection differ'

        print(f'PASS: {args.cycles} rapid tab/theme/resize cycles; compact form/settings fit; setup collapse, viewport bounds and mapped controls verified (Tk scale {root.tk.call("tk","scaling")}).',flush=True)
    finally:
        if app:app.tray.close();app.executor.shutdown(wait=True)
        root.destroy()

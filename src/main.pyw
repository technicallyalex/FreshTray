"""FreshTray Qt Quick launcher. User data stays compatible with the Tk build."""
import argparse
import os
from pathlib import Path
import sys

# The copied helper must run without initializing Qt or the single-instance guard.
if __name__ == '__main__' and len(sys.argv)==3 and sys.argv[1]=='--apply-update':
    from freshtray.updates import apply_plan
    try:
        sys.exit(0 if apply_plan(sys.argv[2]) else 1)
    except Exception:
        sys.exit(1)

from PySide6.QtCore import QUrl, QTimer, Qt, QCoreApplication, QEvent
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from freshtray.api import FreshBooks
from freshtray.demo import Demo
from freshtray.storage import Vault, Preferences
from freshtray.qt_app import Controller
from freshtray.windows import SingleInstance


def main():
    parser = argparse.ArgumentParser(description='FreshTray personal Windows time logger')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--background', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--qa-wizard',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--qa-panels',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--qa-billing',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--qa-live-readonly',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--update-receipt', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.qa_wizard and not args.data_dir:parser.error('--qa-wizard requires an isolated --data-dir')
    if args.qa_panels and not args.data_dir:parser.error('--qa-panels requires an isolated --data-dir')
    if args.qa_billing and (not args.data_dir or args.qa_panels or args.qa_wizard or args.demo):
        parser.error('--qa-billing requires an isolated --data-dir and runs by itself')
    if args.qa_live_readonly and (not (args.qa_panels or args.qa_billing) or args.demo):
        parser.error('--qa-live-readonly requires a supported isolated diagnostic without --demo')
    if args.qa_wizard or args.qa_panels or args.qa_billing:
        local = Path(os.environ['LOCALAPPDATA']).resolve()
        selected = args.data_dir.resolve()
        if any(selected.is_relative_to((local / name).resolve()) for name in ('FreshTray', 'FreshTray-Preview')):
            parser.error('Diagnostics cannot use the normal FreshTray profile. Use an isolated copy.')
    # Qt 6 owns per-monitor DPI awareness. Do not set Tk/Win32 scaling overrides.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    application = QApplication(sys.argv)
    application.setApplicationName('FreshTray')
    application.setOrganizationName('FreshTray')
    application.setQuitOnLastWindowClosed(False)
    QQuickStyle.setStyle('Basic')
    instance = SingleInstance(args.demo or args.qa_wizard or args.qa_panels or args.qa_billing)
    if instance.exists:
        QMessageBox.information(None, 'FreshTray', 'FreshTray is already running. Open it from the system tray, or quit the old build before launching the new one.')
        instance.close()
        return 0
    controller = None
    engine = None
    try:
        folder = args.data_dir or Path(os.environ['LOCALAPPDATA']) / ('FreshTray-Preview' if args.demo else 'FreshTray')
        vault, prefs = Vault(folder/'vault.dpapi'), Preferences(folder/'settings.json')
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        application.setWindowIcon(QIcon(str(base/'assets/freshtray.ico')))
        for font in (base/'assets/fonts').glob('*.ttf'):
            QFontDatabase.addApplicationFont(str(font))
        if args.qa_live_readonly:
            from freshtray.live_readonly import LiveReadOnlyTransport
            provider=FreshBooks(vault,transport=LiveReadOnlyTransport())
        elif (args.qa_wizard or args.qa_panels or args.qa_billing) and not args.demo:
            from freshtray.api import ApiError
            def no_network(*args,**kwargs):raise ApiError('Offline diagnostic: network disabled.',uncertain=True)
            provider=FreshBooks(vault,transport=no_network)
        else:provider=Demo() if args.demo else FreshBooks(vault)
        controller = Controller(provider, vault, prefs, base/'assets', Path(__file__), args.demo)
        if args.qa_wizard or args.qa_panels or args.qa_billing:
            controller.invoices.billingTools.payment_autosync_enabled = False
            if controller.offline and not args.qa_live_readonly:controller.offline.probe=lambda:False
            controller._updater.offline_mode=True;controller._updater.start_timer.stop()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty('backend', controller)
        engine.load(QUrl.fromLocalFile(str(base/'freshtray/qml/Main.qml')))
        if not engine.rootObjects():
            raise RuntimeError('Interface could not load')
        controller.window = engine.rootObjects()[0]
        controller.apply_window_flags()
        if not args.background:
            controller.window.show()
        QTimer.singleShot(0, controller.start)
        if args.qa_wizard:
            from freshtray.wizard_diagnostic import run_wizard_check
            run_wizard_check(application,controller,engine,args.data_dir)
        if args.qa_panels:
            from freshtray.panel_diagnostic import run_panel_check
            run_panel_check(application,controller,engine,args.data_dir,live_readonly=args.qa_live_readonly)
        if args.qa_billing:
            from freshtray.billing_diagnostic import run_billing_check
            run_billing_check(application, controller, controller.window, args.data_dir, args.qa_live_readonly)
        if args.update_receipt:
            from freshtray.updates import mark_ready
            def acknowledge_update():
                try:mark_ready(args.update_receipt,sys.executable)
                except (OSError,ValueError):application.exit(1)
            QTimer.singleShot(1200,acknowledge_update)
        result = application.exec()
        controller.invoices.close()
        controller._updater.close()
        controller.popup_chime.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        controller.local_executor.shutdown(wait=True)
        controller.executor.shutdown(wait=True)
        return result
    except Exception:
        QMessageBox.critical(None, 'FreshTray could not start', 'Try a fresh copy of the executable and check that this Windows account can open its encrypted settings. Your existing account data has not been removed.')
        if controller:
            controller.invoices.close()
            controller._updater.close()
            controller.popup_chime.close()
            controller.local_executor.shutdown(wait=False, cancel_futures=True)
            controller.executor.shutdown(wait=False, cancel_futures=True)
        return 1
    finally:
        instance.close()


if __name__ == '__main__':
    sys.exit(main())

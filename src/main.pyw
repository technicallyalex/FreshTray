"""FreshTray Qt Quick launcher. User data stays compatible with the Tk build."""
import argparse
import os
from pathlib import Path
import sys

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
    args = parser.parse_args()
    # Qt 6 owns per-monitor DPI awareness. Do not set Tk/Win32 scaling overrides.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    application = QApplication(sys.argv)
    application.setApplicationName('FreshTray')
    application.setOrganizationName('FreshTray')
    application.setQuitOnLastWindowClosed(False)
    QQuickStyle.setStyle('Basic')
    instance = SingleInstance(args.demo)
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
        controller = Controller(Demo() if args.demo else FreshBooks(vault), vault, prefs, base/'assets', Path(__file__), args.demo)
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
        result = application.exec()
        controller.popup_chime.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        controller.local_executor.shutdown(wait=True)
        controller.executor.shutdown(wait=True)
        return result
    except Exception:
        QMessageBox.critical(None, 'FreshTray could not start', 'Try a fresh copy of the executable and check that this Windows account can open its encrypted settings. Your existing account data has not been removed.')
        if controller:
            controller.popup_chime.close()
            controller.local_executor.shutdown(wait=False, cancel_futures=True)
            controller.executor.shutdown(wait=False, cancel_futures=True)
        return 1
    finally:
        instance.close()


if __name__ == '__main__':
    sys.exit(main())

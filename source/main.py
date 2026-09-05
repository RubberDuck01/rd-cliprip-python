import sys
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from rd_cliprip.models.config import Config
from rd_cliprip.models.stats import Stats
from rd_cliprip.controllers.download_manager import DownloadManager
from rd_cliprip.controllers.main_controller import MainController
from rd_cliprip.services.network import NetworkMonitor
from rd_cliprip.ui.main_window import MainWindow
from rd_cliprip.resources import get_resources_dir


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Rubber Duck's ClipRip")

    icon_path = get_resources_dir() / "rd_cliprip_logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = Config()
    stats = Stats()
    stats.register_session()

    manager = DownloadManager(config, stats)
    session = manager.load_last_session()
    if session is None:
        manager.new_session(config.downloads_dir)

    network_monitor = NetworkMonitor()

    window = MainWindow(config, stats, manager, network_monitor=network_monitor)
    controller = MainController(window)
    window.controller = controller

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

import re

import adbutils
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QApplication

from .ui import Ui_Connector


class Connector:

    @staticmethod
    def show_startup_dialog() -> QMessageBox:
        startup_window = QMessageBox()
        startup_window.setText('Loading ADB...')

        for button in startup_window.buttons():
            button.hide()

        startup_window.show()
        QApplication.processEvents()
        return startup_window

    @staticmethod
    def show_dialog() -> tuple[int, str, str]:
        dialog = QDialog()
        ui = Ui_Connector()
        ui.setupUi(dialog)

        port_validator = QIntValidator(1, 65535)

        ui.port_editor.setValidator(port_validator)

        return dialog.exec_(), ui.ip_selector.currentText(), ui.port_editor.text()

    @staticmethod
    def check_ipv4(ipv4: str):
        return re.match(
            r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$',
            ipv4.strip()
        )

    @staticmethod
    def try_connect() -> bool:
        startup_window = Connector.show_startup_dialog()

        devices = adbutils.adb.device_list()

        startup_window.close()
        startup_window.deleteLater()

        if devices:
            return True

        button, ip, port = Connector.show_dialog()
        if button == QDialogButtonBox.StandardButton.Cancel:
            return False
        elif not Connector.check_ipv4(ip):
            return False

        try:
            msg = adbutils.adb.connect(f"{ip.strip()}:{port.strip()}")
            if "unable" in msg or "failed" in msg:
                return False
            return True
        except adbutils.AdbTimeout:
            return False

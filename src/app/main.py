import sys
from argparse import ArgumentParser
from typing import Optional

import av
from PySide6 import QtCore
from PySide6.QtCore import QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent, QCursor
from PySide6.QtNetwork import QTcpSocket
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from adbutils import adb

import src.scrcpy as scrcpy
from .qt_scrcpy import QScrcpyClient
from .frame_viewer import FrameViewer
from .logger import Logger
from .ui import Ui_MainWindow
from .utils.fps_counter import FPSCounter
from .utils.mouse_recorder import MouseRecorder

serial = "NULL"


def get_formatted_bitrate(bitrate):
    if bitrate < 2**10:
        return f"{bitrate} bps"
    elif bitrate < 2**20:
        return f"{bitrate / 2 ** 10:.2f} Kbps"
    elif bitrate < 2**30:
        return f"{bitrate / 2 ** 20:.2f} Mbps"
    else:
        return f"{bitrate / 2 ** 30:.2f} Gbps"


class MainWindow(QMainWindow):
    onMouseReleased = QtCore.Signal(QPoint)

    def __init__(
        self,
        max_width: Optional[int],
        serial: Optional[str] = None,
        encoder_name: Optional[str] = None,
        max_fps: Optional[int] = None,
        bitrate: Optional[int] = None,
    ):
        super(MainWindow, self).__init__()
        self.serial = serial
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.max_width = max_width
        self.logger = Logger.get_logger()

        # Setup devices
        self.devices = self.list_devices()
        if serial:
            self.choose_device(serial)
        self.device = adb.device(serial=self.ui.combo_device.currentText())
        self.alive = True

        # Setup client
        self.client = QScrcpyClient(
            device=self.device,
            flip=self.ui.flip.isChecked(),
            bitrate=bitrate or 1_000_000_000,
            max_fps=max_fps or 30,
            encoder_name=encoder_name,
        )
        self.client.add_listener(scrcpy.EVENT_INIT, self.on_init)
        self.client.add_listener(scrcpy.EVENT_FRAME, self.on_frame)
        self.client.add_listener(scrcpy.EVENT_DISCONNECT, self.on_disconnected)

        # Setup developer tools
        self.mouse_recorder = MouseRecorder()
        self.onMouseReleased.connect(self.mouse_recorder_handler)

        # Bind controllers
        self.ui.button_home.clicked.connect(self.on_click_home)
        self.ui.button_back.clicked.connect(self.on_click_back)
        self.ui.button_switch.clicked.connect(self.on_click_switch)

        self.ui.button_record_click.clicked.connect(self.on_click_record_click)
        self.ui.button_take_region.clicked.connect(self.on_click_take_region_screenshot)
        self.ui.button_show_log.clicked.connect(self.logger.show)

        self.ui.button_screen_on.clicked.connect(self.on_click_screen_on)
        self.ui.button_screen_off.clicked.connect(self.on_click_screen_off)

        # Bind config
        self.ui.combo_device.currentTextChanged.connect(self.choose_device)
        self.ui.flip.stateChanged.connect(self.on_flip)

        # Bind mouse event
        self.ui.opengl_widget.mousePressEvent = self.on_mouse_event(scrcpy.ACTION_DOWN)
        self.ui.opengl_widget.mouseMoveEvent = self.on_mouse_event(scrcpy.ACTION_MOVE)
        self.ui.opengl_widget.mouseReleaseEvent = self.on_mouse_event(scrcpy.ACTION_UP)
        self.ui.opengl_widget.wheelEvent = self.on_mouse_wheel_event

        # Keyboard event
        self.keyPressEvent = self.on_key_event(scrcpy.ACTION_DOWN)
        self.keyReleaseEvent = self.on_key_event(scrcpy.ACTION_UP)

        # setup ui elements
        bitrate = self.client.bitrate
        self.ui.label_rate.setText(get_formatted_bitrate(bitrate))
        self.ui.label_encoder.setText(self.client.encoder_name or "Auto")
        self.client.onFrameResized.connect(
            lambda w, h: {self.ui.label_resolution.setText(f"{w} * {h}")}
        )
        # move to left top
        self.move(0, 0)

        # region selector
        self.region_selector = None

        # screen
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()
        self.last_ratio = 1
        self.delta_size = None

        # mouse tracer
        self.mouse_trace_timer = QtCore.QTimer()
        self.mouse_trace_timer.setInterval(50)
        self.mouse_trace_timer.timeout.connect(self.update_mouse_trace)
        self.mouse_trace_timer.start()

        # fps counter
        self.fps_counter = FPSCounter()
        self.fps_counter.onFps.connect(self.ui.label_fps.setText)

    def choose_device(self, device):
        global serial
        if device not in self.devices:
            msgBox = QMessageBox()
            msgBox.setText(f"Device serial [{device}] not found!")
            msgBox.exec()
            return

        # Ensure text
        self.ui.combo_device.setCurrentText(device)
        # Restart service
        if getattr(self, "client", None):
            self.client.change_device(device)

    def list_devices(self):
        self.ui.combo_device.clear()
        items = [i.serial for i in adb.device_list()]
        self.ui.combo_device.addItems(items)
        return items

    def on_flip(self, _):
        self.client.flip = self.ui.flip.isChecked()

    def on_click_home(self):
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_DOWN)
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_UP)
        self.logger.info("Home clicked")

    def on_click_back(self):
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_DOWN)
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_UP)
        self.logger.info("Back clicked")

    def on_click_switch(self):
        self.client.control.keycode(scrcpy.KEYCODE_APP_SWITCH, scrcpy.ACTION_DOWN)
        self.client.control.keycode(scrcpy.KEYCODE_APP_SWITCH, scrcpy.ACTION_UP)
        self.logger.info("Switch clicked")

    def on_click_screen_on(self):
        # enable phone screen
        self.client.control.set_screen_power_mode(scrcpy.POWER_MODE_NORMAL)

    def on_click_screen_off(self):
        # disable screen
        self.client.control.set_screen_power_mode(scrcpy.POWER_MODE_OFF)

    def on_click_record_click(self):
        if not self.mouse_recorder.is_recording:
            self.mouse_recorder.start_record()
            self.ui.button_record_click.setText("Stop Recording Clicks")
            print(self.ui.button_record_click.styleSheet())
            self.ui.button_record_click.setStyleSheet("background-color: red")
            self.logger.info("Start record click event", self.mouse_recorder)
        else:
            self.mouse_recorder.stop_record()
            self.ui.button_record_click.setText("Start Recording Clicks")
            self.ui.button_record_click.setStyleSheet("background-color: green")
            self.logger.info("Stop record click event", self.mouse_recorder)
            QMessageBox.information(
                self,
                "鼠标记录",
                f"鼠标记录已经保存在{self.mouse_recorder.save_dir}目录下的mouse_records.txt中",
            )

    def on_click_take_region_screenshot(self):
        self.region_selector = FrameViewer()
        self.region_selector.show()
        pix = self.ui.opengl_widget.screenShot()
        self.region_selector.set_pixmap(pix)
        del pix

    def on_mouse_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QMouseEvent):
            focused_widget = QApplication.focusWidget()
            if focused_widget is not None:
                focused_widget.clearFocus()
            x_ratio = self.client.resolution[0] / self.ui.opengl_widget.width()
            y_ratio = self.client.resolution[1] / self.ui.opengl_widget.height()
            mouse_x = round(evt.position().x() * x_ratio)
            mouse_y = round(evt.position().y() * y_ratio)
            self.client.control.touch(mouse_x, mouse_y, action)
            pos = QPoint(mouse_x, mouse_y)

            # if is release, call on_mouse_released
            if action == scrcpy.ACTION_UP:
                self.onMouseReleased.emit(pos)

        return handler

    def update_mouse_trace(self):
        # if mouse in self.ui.opengl_widget
        if self.ui.opengl_widget.underMouse():
            # get relative position of mouse
            _pos = self.ui.opengl_widget.mapFromGlobal(QCursor.pos())
            x_ratio = self.client.resolution[0] / self.ui.opengl_widget.width()
            y_ratio = self.client.resolution[1] / self.ui.opengl_widget.height()
            mouse_x = round(_pos.x() * x_ratio)
            mouse_y = round(_pos.y() * y_ratio)
            pos = QPoint(mouse_x, mouse_y)
            self.on_mouse_moved(pos)

    def on_mouse_wheel_event(self, evt: QWheelEvent):
        x_ratio = self.client.resolution[0] / self.ui.opengl_widget.width()
        y_ratio = self.client.resolution[1] / self.ui.opengl_widget.height()
        mouse_x = round(evt.position().x() * x_ratio)
        mouse_y = round(evt.position().y() * y_ratio)
        self.client.control.scroll(
            mouse_x,
            mouse_y,
            0,
            evt.angleDelta().y() / 60,
        )

    def on_mouse_moved(self, pos: QPoint):
        self.ui.label_mouse_pos.setText(f"{pos.x()}, {pos.y()}")

    def on_key_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QKeyEvent):
            code = self.map_code(evt.key())
            if code != -1:
                self.client.control.keycode(code, action)

        return handler

    def mouse_recorder_handler(self, pos: QPoint):
        if self.mouse_recorder.is_recording:
            self.mouse_recorder.on_mouse_released(
                pos, self.ui.opengl_widget.screenShot()
            )

    def map_code(self, code):
        """
        Map qt keycode ti android keycode

        Args:
            code: qt keycode
            android keycode, -1 if not founded
        """

        if code == -1:
            return -1
        if 48 <= code <= 57:
            return code - 48 + 7
        if 65 <= code <= 90:
            return code - 65 + 29
        if 97 <= code <= 122:
            return code - 97 + 29

        hard_code = {
            32: scrcpy.KEYCODE_SPACE,
            16777219: scrcpy.KEYCODE_DEL,
            16777248: scrcpy.KEYCODE_SHIFT_LEFT,
            16777220: scrcpy.KEYCODE_ENTER,
            16777217: scrcpy.KEYCODE_TAB,
            16777249: scrcpy.KEYCODE_CTRL_LEFT,
        }
        if code in hard_code:
            return hard_code[code]

        print(f"Unknown keycode: {code}")
        return -1

    def on_init(self):
        self.setWindowTitle(f"Serial: {self.client.device_name}")

    def resizeEvent(self, event):
        if self.delta_size is None:
            return super().resizeEvent(event)
        width = event.size().width()
        max_width = width - self.delta_size.width()
        gl_height = round(max_width / self.last_ratio)
        if gl_height > self.screen_height:
            gl_height = self.screen_height
            max_width = round(gl_height * self.last_ratio)

        self.resize(
            max_width + self.delta_size.width(),
            gl_height + self.delta_size.height(),
        )
        self.ui.opengl_widget.resize(max_width, gl_height)
        self.ui.opengl_widget.update()

    def on_frame(self, frame: av.VideoFrame):
        if frame is not None:
            self.fps_counter.hint()
            self.ui.opengl_widget.setFrame(frame)
            ratio = frame.width / frame.height
            if abs(self.last_ratio - ratio) > 0.01:
                self.last_ratio = ratio
                self.delta_size = self.size() - self.ui.opengl_widget.size()
                gl_width = self.max_width
                gl_height = round(gl_width / ratio)
                if gl_height > self.screen_height:
                    gl_height = self.screen_height
                    gl_width = round(gl_height * ratio)

                self.ui.opengl_widget.resize(gl_width, gl_height)
                self.resize(
                    gl_width + self.delta_size.width(),
                    gl_height + self.delta_size.height(),
                )
                print(f"Resize to {gl_width} * {gl_height}")
                QApplication.processEvents()

    def on_socket_error(self, socketError: QTcpSocket.SocketError):
        self.logger.error(f"Socket error: {socketError}")
        if self.client.alive:
            self.client.stop()

    def on_resolution_changed(self, width, height):
        self.client.resolution = (width, height)

    def on_disconnected(self):
        self.logger.info(f"Disconnected from device: {self.client.device_name}")
        if self.client.last_socket_error is not None:
            QMessageBox.information(
                self,
                "Disconnected",
                f"Disconnected from device: {self.client.device_name}, please check your device:\n\n{self.client.last_socket_error}",
            )
            self.client.last_socket_error = None
        self.close()

    def closeEvent(self, _):
        self.close_window()
        QApplication.instance().exit(0)

    def close_window(self):
        self.mouse_recorder.stop_record()
        if self.client.alive:
            self.client.stop()
        self.mouse_trace_timer.stop()
        self.alive = False
        self.mouse_recorder.stop_processor()


def main():
    global serial
    parser = ArgumentParser(
        description="A simple scrcpy client",
    )
    parser.add_argument(
        "-m",
        "--max_width",
        type=int,
        default=960,
        help="Set max width of the window, default 1280",
    )
    parser.add_argument(
        "-d",
        "--device",
        type=str,
        help="Select device manually (device serial required)",
    )
    parser.add_argument(
        "-s",
        "--max_fps",
        type=int,
        default=60,
        help="Set max fps of the window, default 30, 30 ~ 60 is recommended",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        type=int,
        default=8_000_000,
        help="Set bitrate of the video, default 8Mbps",
    )
    parser.add_argument("--encoder_name", type=str, help="Encoder name to use")
    args = parser.parse_args()
    serial = args.device

    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication([])
    app.setApplicationName("PyScrcpyClient")
    try:
        m = MainWindow(
            args.max_width, serial, args.encoder_name, args.max_fps, args.bitrate
        )
    except RuntimeError as e:
        QMessageBox.critical(
            None,
            "ADB Error",
            e.args[0],
            QMessageBox.StandardButton.Ok,
        )
        return
    m.show()
    m.client.async_start()
    sys.exit(app.exec())

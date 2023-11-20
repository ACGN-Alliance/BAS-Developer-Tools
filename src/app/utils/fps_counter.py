from PySide6 import QtCore
from PySide6.QtCore import QObject


class FPSCounter(QObject):
    onFps = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.fps = 0
        self.frame_count = 0
        self.count_interval = 1000
        self.count_timer = QtCore.QTimer()
        self.count_timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.count_timer.setInterval(self.count_interval)
        self.count_timer.timeout.connect(self.update_fps)
        self.count_mutex = QtCore.QMutex()
        self.count_timer.start()
        self.updating_fps = False

    def update_fps(self):
        self.updating_fps = True
        self.fps = self.frame_count
        self.frame_count = 0
        self.updating_fps = False
        self.onFps.emit(str(self.fps))

    def hint(self):
        while self.updating_fps:
            pass
        self.frame_count += 1

    def stop(self):
        self.count_timer.stop()

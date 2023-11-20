import time

import PIL.Image
import av
from PySide6.QtCore import QThread, Signal, QMutex
from PySide6.QtGui import Qt

from .qyuvopenglwidget import QYUVOpenGLWidget

ATTRIB_VERTEX = 3
ATTRIB_TEXTURE = 4


class YUVOpenGLWidget(QYUVOpenGLWidget):
    def __init__(self, parent):
        QYUVOpenGLWidget.__init__(self, parent)
        self.m_screenShot = QMutex()

    def setFrame(self, pBufYuv420p: av.video.frame.VideoFrame):
        """
        使用av库的VideoFrame对象更新帧
        Args:
            pBufYuv420p:

        Returns:

        """
        if pBufYuv420p is None:
            return None
        self.m_screenShot.lock()
        self.m_pBufYuv420p = pBufYuv420p
        self.m_screenShot.unlock()
        self.update()

    def screenShot(self):
        b = time.time()
        self.m_screenShot.lock()
        frame: PIL.Image.Image = self.m_pBufYuv420p.to_image()
        self.m_screenShot.unlock()
        pix = frame.toqpixmap()
        print(f"screenShot cost: {time.time() - b}")
        return pix


class DecodeWorker(QThread):
    frameReady = Signal(av.video.frame.VideoFrame)
    fpsUpdated = Signal(str)

    def __init__(self, file):
        super().__init__()
        self.file = file
        self.frameCountWnd = 50

    def run(self):
        container = av.open(self.file)
        count = 0
        lastFrameTime = time.time()
        for frame in container.decode(video=0):
            if frame.format.name != "yuv420p":
                frame = frame.reformat(format="yuv420p")
                print("reformatted")
            count += 1

            if count > self.frameCountWnd:  # update fps
                count = 0
                now = time.time()
                fps = self.frameCountWnd / (now - lastFrameTime)
                lastFrameTime = now
                self.fpsUpdated.emit(f"{fps:.2f} fps")
            self.msleep(1000 // 60 - 2)
            self.frameReady.emit(frame)


if __name__ == "__main__":
    VIDEO_FILE = "test.mp4"

    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    window = QMainWindow()
    ui = YUVOpenGLWidget(window)
    window.setCentralWidget(ui)
    window.show()
    window.resize(1280, 720)
    worker = DecodeWorker(VIDEO_FILE)
    worker.frameReady.connect(
        ui.setFrame, type=Qt.ConnectionType.BlockingQueuedConnection
    )
    worker.fpsUpdated.connect(window.setWindowTitle)
    worker.start()
    app.exec()

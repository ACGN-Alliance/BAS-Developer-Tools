import datetime
import json
import os
import zipfile
from typing import Optional

from PIL import Image, ImageDraw
from PySide6 import QtCore
from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QPixmap

from ..logger import Logger


class MouseRecord:
    def __init__(self, pos: QPoint, frame: QPixmap):
        super().__init__()
        self.pos = pos
        self.frame = frame


class MouseRecordProcessor(QObject):
    onRecordSaved = QtCore.Signal(str, int, int)
    onMouseRecorded = QtCore.Signal(MouseRecord)

    def __init__(self, save_dir: str):
        super().__init__()
        self.count = 0
        self.save_dir = save_dir  # 保存目录
        self.onMouseRecorded.connect(self.record_process)
        self.dump_time_indicator()

    def dump_time_indicator(self):
        os.makedirs(self.save_dir, exist_ok=True)
        indicator = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
        with open(
            f"{self.save_dir}/TIME_INDICATOR~{indicator}", "w", encoding="utf-8"
        ) as f:
            f.write(f"TIME_INDICATOR~{indicator}\n")

    def record_process(self, record: MouseRecord) -> None:
        self.count += 1
        record_name = f"mouse_record_{self.count}"
        pos, pix = record.pos, record.frame
        # 在frame的pos处绘制一个长宽20pixel,厚度为2pixel的红色十字
        # 1. 获取frame的shape
        # 2. 计算十字的起始点和终止点
        # 3. 绘制十字
        # 4. 保存frame
        pix: QPixmap
        img: Image.Image = Image.fromqpixmap(pix)
        height, width = pix.height(), pix.width()

        # 绘制一个竖着的线
        img_draw = ImageDraw.Draw(img)
        img_draw.line((pos.x(), 0, pos.x(), height), fill=(255, 0, 0), width=2)

        # 绘制一个横着的线
        img_draw.line((0, pos.y(), width, pos.y()), fill=(255, 0, 0), width=2)

        os.makedirs(self.save_dir, exist_ok=True)
        # 保存pix
        img.save(f"{self.save_dir}/{record_name}.png")
        # 保存记录
        with open(f"{self.save_dir}/mouse_records.txt", "a", encoding="utf-8") as f:
            data = json.dumps(
                {
                    "name": record_name,
                    "pos": [int(pos.x()), int(pos.y())],
                    "window_size": [width, height],
                    "relative_pos": [
                        int(100 * pos.x() / width),
                        int(100 * pos.y() / height),
                    ],
                    "frame": f"{record_name}.png",
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[
                        :-3
                    ],
                },
                ensure_ascii=False,
            )
            f.write(data + "\n")

        self.onRecordSaved.emit(record_name, pos.x(), pos.y())


class MouseRecorder(QObject):
    def __init__(self, save_dir: Optional[str] = None):
        super().__init__()
        self.logger = Logger.get_logger()
        self.__is_recording = False
        self.save_dir = save_dir or "mouse_records"
        self.make_archive()
        self.processor = MouseRecordProcessor(save_dir=self.save_dir)
        self.work_thread = QtCore.QThread()
        self.processor.moveToThread(self.work_thread)

        self.work_thread.started.connect(self.on_process_started)
        self.processor.onRecordSaved.connect(self.on_processor_saved)
        self.work_thread.start()

    def make_archive(self):
        if os.path.exists(self.save_dir):
            time_indicator = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")[
                :-3
            ]  # default time indicator
            files_to_zip = []
            time_indicator_file = None
            for _ in os.listdir(self.save_dir):
                if _.startswith("TIME_INDICATOR~"):
                    time_indicator = _.split("~")[1]  # get the latest time indicator
                    time_indicator_file = _
                elif not _.endswith(".zip"):
                    files_to_zip.append(_)  # add all files except zip files

            if time_indicator_file is not None:
                os.remove(os.path.join(self.save_dir, time_indicator_file))

            if len(files_to_zip) == 0:
                return

            archive_name = f"mouse_records_{time_indicator}.zip"
            self.logger.info(
                msg=f"Making archive: {archive_name=}",
                sender=self,
            )
            with zipfile.ZipFile(
                os.path.join(self.save_dir, archive_name), "w"
            ) as zip_file:
                for _ in files_to_zip:
                    zip_file.write(os.path.join(self.save_dir, _), _)
            # clean all files
            for _ in files_to_zip:
                os.remove(os.path.join(self.save_dir, _))
        else:
            self.logger.info(
                msg=f"Archive not made: {self.save_dir=} does not exist",
                sender=self,
            )

    def on_mouse_released(self, pos: QPoint, pix: QPixmap):
        if self.__is_recording:
            if pix is None:
                return
            self.processor.onMouseRecorded.emit(MouseRecord(pos, pix))

    def on_process_started(self):
        self.logger.debug(msg="thread started", sender=self)

    def on_processor_saved(self, name: str, x: int, y: int):
        self.logger.success(
            msg=f"Mouse Click Event Recorded: {name=} ({x=}, {y=})",
            sender=self,
        )

    def start_record(self):
        self.__is_recording = True

    def stop_record(self):
        self.__is_recording = False

    def stop_processor(self):
        self.work_thread.quit()
        self.work_thread.wait()

    @property
    def is_recording(self):
        return self.__is_recording

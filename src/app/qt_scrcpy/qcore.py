import os
import socket
import struct
import threading
from time import sleep
from typing import Any, Callable, Optional, Tuple, Union

import av
from adbutils import AdbConnection, AdbDevice, AdbError, Network, adb

from src.scrcpy.const import (
    EVENT_DISCONNECT,
    EVENT_INIT,
    LOCK_SCREEN_ORIENTATION_UNLOCKED,
)
from src.scrcpy.control import ControlSender

try:
    from PySide6.QtNetwork import QTcpSocket
    from PySide6.QtCore import QObject, QByteArray, Signal, QThread, SignalInstance, Qt
except ImportError:
    raise ImportError("PySide6 is required to use QScrcpyClient")


class VideoDecoder(QObject):
    onDataReceived = Signal(QByteArray)
    onFrameReady = Signal(object)
    onResolutionChanged = Signal(int, int)
    resolution = (-1, -1)

    def __init__(self):
        super().__init__()
        self.codec = av.CodecContext.create("h264", "r")
        self.onDataReceived.connect(self.parse_data)

    def parse_data(self, data: QByteArray):
        packets = self.codec.parse(data.data())
        if not packets:
            return
        for packet in packets:
            frames = self.codec.decode(packet)
            for raw_frame in frames:
                self.onFrameReady.emit(raw_frame)
                width, height = raw_frame.width, raw_frame.height
                if width != self.resolution[0] or height != self.resolution[1]:
                    self.resolution = (width, height)
                    self.onResolutionChanged.emit(width, height)


class QScrcpyClient(QObject):
    onFrameResized = Signal(int, int)
    onFrameReady = Signal(av.VideoFrame)
    onInit = Signal()
    onDisconnect = Signal()

    def __init__(
        self,
        device: Optional[Union[AdbDevice, str, any]] = None,
        max_width: int = 0,
        bitrate: int = 8000000,
        max_fps: int = 0,
        flip: bool = False,
        block_frame: bool = False,
        stay_awake: bool = False,
        lock_screen_orientation: int = LOCK_SCREEN_ORIENTATION_UNLOCKED,
        connection_timeout: int = 3000,
        encoder_name: Optional[str] = None,
        receive_buffer_size: int = 0x10000,
    ):
        """
        Create a scrcpy client, this client won't be started until you call the start function

        Args:
            device: Android device, select first one if none, from serial if str
            max_width: frame width that will be broadcast from android server
            bitrate: bitrate
            max_fps: maximum fps, 0 means not limited (supported after android 10)
            flip: flip the video
            block_frame: only return nonempty frames, may block cv2 render thread
            stay_awake: keep Android device awake
            lock_screen_orientation: lock screen orientation, LOCK_SCREEN_ORIENTATION_*
            connection_timeout: timeout for connection, unit is ms
            encoder_name: encoder name, enum: [OMX.google.h264.encoder, OMX.qcom.video.encoder.avc, c2.qti.avc.encoder, c2.android.avc.encoder], default is None (Auto)
            receive_buffer_size: receive buffer size, default is 0x10000
        """
        super().__init__()
        # Check Params
        assert max_width >= 0, "max_width must be greater than or equal to 0"
        assert bitrate >= 0, "bitrate must be greater than or equal to 0"
        assert max_fps >= 0, "max_fps must be greater than or equal to 0"
        assert (
            -1 <= lock_screen_orientation <= 3
        ), "lock_screen_orientation must be LOCK_SCREEN_ORIENTATION_*"
        assert (
            connection_timeout >= 0
        ), "connection_timeout must be greater than or equal to 0"
        assert encoder_name in [
            None,
            "OMX.google.h264.encoder",
            "OMX.qcom.video.encoder.avc",
            "c2.qti.avc.encoder",
            "c2.android.avc.encoder",
        ]

        # Params
        self.flip = flip
        self.max_width = max_width
        self.bitrate = bitrate
        self.max_fps = max_fps
        self.block_frame = block_frame
        self.stay_awake = stay_awake
        self.lock_screen_orientation = lock_screen_orientation
        self.connection_timeout = connection_timeout
        self.encoder_name = encoder_name
        self.receive_buffer_size = receive_buffer_size

        # Connect to device
        if device is None:
            device = adb.device_list()[0]
        elif isinstance(device, str):
            device = adb.buffer(serial=device)

        self.device = device
        self.listeners = dict(frame=[], init=[], disconnect=[])
        self.listener_signal = {
            "frame": self.onFrameReady,
            "init": self.onInit,
            "disconnect": self.onDisconnect,
        }

        # User accessible
        self.last_frame: Optional[av.VideoFrame] = None
        self.resolution: Optional[Tuple[int, int]] = None
        self.device_name: Optional[str] = None
        self.control = ControlSender(self)

        # Need to destroy
        self.alive = False
        self.__server_stream: Optional[AdbConnection] = None
        self.__video_socket: Optional[socket.socket] = None
        self.control_socket: Optional[socket.socket] = None
        self.control_socket_lock = threading.Lock()

        # Qt stuff
        self.q_socket: Optional[QTcpSocket] = None
        self.video_decoder = VideoDecoder()
        self.video_decoder_thread = QThread()
        self.last_socket_error = None

    def __init_server_connection(self) -> None:
        """
        Connect to android server, there will be two sockets, video and control socket.
        This method will set: video_socket, control_socket, resolution variables
        """
        for _ in range(self.connection_timeout // 100):
            try:
                self.__video_socket = self.device.create_connection(
                    Network.LOCAL_ABSTRACT, "scrcpy"
                )
                break
            except AdbError:
                sleep(0.1)
                pass
        else:
            raise ConnectionError("Failed to connect scrcpy-server after 3 seconds")

        dummy_byte = self.__video_socket.recv(1)
        if not len(dummy_byte) or dummy_byte != b"\x00":
            raise ConnectionError("Did not receive Dummy Byte!")

        self.control_socket = self.device.create_connection(
            Network.LOCAL_ABSTRACT, "scrcpy"
        )
        self.device_name = self.__video_socket.recv(64).decode("utf-8").rstrip("\x00")
        if not len(self.device_name):
            raise ConnectionError("Did not receive Device Name!")

        res = self.__video_socket.recv(4)
        self.resolution = struct.unpack(">HH", res)
        self.onFrameResized.emit(self.resolution[0], self.resolution[1])
        self.__video_socket.setblocking(False)

    def __deploy_server(self) -> None:
        """
        Deploy server to android device
        """
        jar_name = "scrcpy-server.jar"
        server_file_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), jar_name
        )
        self.device.sync.push(server_file_path, f"/data/local/tmp/{jar_name}")
        commands = [
            f"CLASSPATH=/data/local/tmp/{jar_name}",
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            "1.20",  # Scrcpy server version
            "info",  # Log level: info, verbose...
            f"{self.max_width}",  # Max screen width (long side)
            f"{self.bitrate}",  # Bitrate of video
            f"{self.max_fps}",  # Max frame per second
            f"{self.lock_screen_orientation}",  # Lock screen orientation: LOCK_SCREEN_ORIENTATION
            "true",  # Tunnel forward
            "-",  # Crop screen
            "false",  # Send frame rate to client
            "true",  # Control enabled
            "0",  # Display id
            "false",  # Show touches
            "true" if self.stay_awake else "false",  # Stay awake
            "-",  # Codec (video encoding) options
            self.encoder_name or "-",  # Encoder name
            "false",  # Power off screen after server closed
        ]

        self.__server_stream: AdbConnection = self.device.shell(
            commands,
            stream=True,
        )

        # Wait for server to start
        self.__server_stream.read(10)

    def make_video_socket(self):

        self.__deploy_server()
        self.__init_server_connection()
        self.__send_to_listeners(EVENT_INIT)
        return self.__video_socket

    def async_start(self) -> None:
        self.last_socket_error = None
        self.alive = True
        self.video_decoder.moveToThread(self.video_decoder_thread)
        for cls in self.listeners["frame"]:
            self.video_decoder.onFrameReady.connect(cls)
        self.video_decoder.onResolutionChanged.connect(self.on_resolution)

        self.video_decoder_thread.start()

        self.q_socket = QTcpSocket()
        self.q_socket.setReadBufferSize(self.receive_buffer_size)

        self.q_socket.readyRead.connect(self.on_q_socket_ready_read)
        self.q_socket.errorOccurred.connect(self.on_q_socket_error)
        self.q_socket.disconnected.connect(self.on_q_socket_disconnected)

        self.q_socket.setSocketDescriptor(self.make_video_socket().fileno())

    def on_resolution(self, width: int, height: int):
        res = (width, height)
        if res != self.resolution:
            self.resolution = res
            self.onFrameResized.emit(width, height)
            print(f"emit:{width},{height}")

    def on_q_socket_ready_read(self):
        data = self.q_socket.readAll()
        self.video_decoder.onDataReceived.emit(data)

    def on_q_socket_disconnected(self):
        self.stop()

    def on_q_socket_error(self, error: QTcpSocket.SocketError):
        self.last_socket_error = error
        self.stop()

    def stop(self) -> None:
        """
        Stop listening (both threaded and blocked)
        """
        self.alive = False
        if self.__server_stream is not None:
            try:
                self.__server_stream.close()
            except Exception:
                pass

        if self.control_socket is not None:
            try:
                self.control_socket.close()
            except Exception:
                pass

        if self.__video_socket is not None:
            try:
                self.__video_socket.close()
            except Exception:
                pass

        if self.video_decoder_thread is not None:
            try:
                self.video_decoder_thread.quit()
                self.video_decoder_thread.wait()
            except Exception:
                pass

        self.__send_to_listeners(EVENT_DISCONNECT)

        # qt stuff
        if self.q_socket is not None:
            try:
                self.q_socket.close()
            except Exception:
                pass

    def add_listener(self, cls: str, listener: Callable[..., Any]) -> None:
        """
        Add a video listener

        Args:
            cls: Listener category, support: init, frame
            listener: A function to receive frame np.ndarray
        """
        self.listeners[cls].append(listener)
        self.listener_signal[cls].connect(listener)

    def remove_listener(self, cls: str, listener: Callable[..., Any]) -> None:
        """
        Remove a video listener

        Args:
            cls: Listener category, support: init, frame
            listener: A function to receive frame np.ndarray
        """
        self.listeners[cls].remove(listener)
        self.listener_signal[cls].disconnect(listener)

    def __send_to_listeners(self, cls: str, *args, **kwargs) -> None:
        """
        Send event to listeners

        Args:
            cls: Listener type
            *args: Other arguments
            *kwargs: Other arguments
        """
        self.listener_signal[cls].emit(*args, **kwargs)
        print(f"send to listeners: {cls=}, {args=}, {kwargs=}")

    def change_device(self, device: str) -> bool:
        alive = self.alive
        self.stop()
        new_device = adb.device(serial=device)
        if new_device is None:
            return False
        self.device = new_device
        if not alive:
            return True

        self.q_socket = None
        self.video_decoder = VideoDecoder()
        self.video_decoder_thread = QThread()
        self.async_start()
        return True

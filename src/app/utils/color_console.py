import builtins
from datetime import datetime


class ColorConsole:
    info = "\033[0;30;47m"  # black
    warn = "\033[0;30;43m"  # orange
    error = "\033[0;30;41m"  # red
    debug = "\033[0;30;44m"  # blue
    critical = "\033[1;37;41m"  # bold red background
    success = "\033[0;30;42m"  # green
    old_print = None

    @classmethod
    def color_print(
        cls, msg, level="INFO", log_time=None, sender=None, *args, **kwargs
    ):
        color = getattr(cls, level.lower())
        log_time = log_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sender = sender or "ColorConsole"
        console_msg = (
            f"{log_time} "
            + f"[{level.upper()}".ljust(8)
            + f"] {sender}".ljust(16)
            + f"::{msg}"
        ).ljust(250)
        cls.old_print(f"{color}{console_msg}\033[0m", *args, **kwargs)

    @classmethod
    def load_print_hook(cls):
        if cls.old_print is None:
            cls.old_print = builtins.print
        builtins.print = cls.color_print

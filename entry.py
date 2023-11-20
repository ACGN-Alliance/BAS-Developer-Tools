import pathlib
import sys

from src.app import main
from src.app.utils.color_console import ColorConsole

if __name__ == "__main__":
    sys.path.append(
        pathlib.Path.cwd().joinpath("OpenGL").absolute().as_posix()
    )  # add OpenGL Library manually
    # redirect print function
    ColorConsole.load_print_hook()
    main()

import argparse
import os
import shutil
import subprocess
import zipfile
import re
from io import BytesIO

from upx import upx_files

run_with_args_bat = """
start ./Lib/entry.exe --max_width 960 --max_fps 60 --bitrate 10000000
"""

script = """
python -m nuitka ^
    --standalone ^
    --assume-yes-for-downloads ^
    --lto=no ^
    --output-dir=build ^
    --company-name="ACGN-Alliance" ^
    --product-name="BlueArchive-Starter-Develop-Tools" ^
    --windows-icon-from-ico=resources/bas.ico ^
    --file-version="$FILE_VERSION$" ^
    --product-version="$FILE_VERSION$" ^
    --windows-file-description="Develop Tools for BAS" ^
    --copyright="Copyright @ACGN-Alliance. All right reserved." ^
    --include-module=OpenGL ^
    --remove-output ^
    --include-package-data=OpenGL ^
    --nofollow-import-to=multiprocessing,viztracer,numpy,cv2 ^
    --windows-disable-console ^
    --enable-plugin=pyside6 ^
    --include-data-file=src/app/qt_scrcpy/scrcpy-server.jar=src/app/qt_scrcpy/scrcpy-server.jar ^
    --msvc=latest ^
    --clang ^
    entry.py
"""


def get_build_script(version):
    # 提取版本号 x.x.x
    version = re.findall(r"\d+\.\d+\.\d+", version)[0]
    _script = script.replace("$FILE_VERSION$", version)
    return _script


def build_main_program(version: str):
    # print("===============================INIT PDM=================================")
    # # init pdm
    # try:
    #     subprocess.run("pdm --version".split(" "))
    # except FileNotFoundError:
    #     subprocess.run("pipx install pdm".split(" "))
    #
    # subprocess.run("pdm sync".split(" "))

    print("===============================BUILD MAIN=================================")
    # write build script
    with open("_nuitka_build.bat", "w", encoding="utf-8") as f:
        f.write(get_build_script(version))
    # build
    subprocess.run("pdm run _nuitka_build.bat".split(" "))
    # delete build script
    os.remove("_nuitka_build.bat")


def get_upx(need_download_upx=False):
    import urllib3
    if not need_download_upx:
        return "upx"
    print("===============================GET UPX=================================")
    if os.path.exists("build\\upx"):
        # delete old upx
        shutil.rmtree("build\\upx")
    # get upx ==> build\upx\upx.exe
    url = "https://github.com/upx/upx/releases/download/v4.2.1/upx-4.2.1-win64.zip"
    file = BytesIO(b"")
    r = urllib3.request("GET", url)
    file.write(r.data)
    file.seek(0)

    with zipfile.ZipFile(file) as f:
        # upx-4.2.1-win64\upx.exe
        f.extractall("build\\upx")
    _upx = "build\\upx\\upx-4.2.1-win64\\upx.exe"
    file.close()
    return _upx


def get_7z():
    import urllib3
    try:
        subprocess.run("7z i")
        print(
            "===============================7Z TEST OK================================="
        )
        return "7z"
    except FileNotFoundError:
        print(
            "===============================7Z DOWNLOADING================================="
        )
        if os.path.exists("build\\7z"):
            # delete old 7z
            shutil.rmtree("build\\7z")
        # get 7z ==> build\7z\7z.exe
        url = "https://7-zip.org/a/7zr.exe"
        file = urllib3.request("GET", url).data
        with open("build\\7z.exe", "wb") as f:
            f.write(file)
        return "build\\7z.exe"


def compress(version,output=None, p7zip=False):
    if not os.path.exists("build\\Lib"):  # only for debug
        # rename build\entry.dist to build\Lib (dir)
        os.rename("build\\entry.dist", "build\\Lib")

    if p7zip:
        print(
            "===============================COMPRESS FILES:7Z================================="
        )
        # max 7z Lib, run_with_args.bat, update_log.txt
        p7zip_exe = get_7z()
        dist_file_name = output or f"BAS-Develop-Tools_{version}_OpenGL.7z"
        subprocess.run(
            f"{p7zip_exe} a -t7z -m0=lzma2 -mx=9 -mfb=64 -md=32m -ms=on -mmt=on -r -y {dist_file_name} Lib run_with_args.bat update_log.txt".split(
                " "
            ),
            cwd="build",
        )
        print(f"7z success: {dist_file_name}")
        print(
            "========================================================================="
        )

    else:
        print(
            "===============================COMPRESS FILES:ZIP================================="
        )
        # max zip Lib, run_with_args.bat, update_log.txt
        dist_file_name = output or f"BAS-Develop-Tools_{version}_OpenGL.zip"
        all_files = []
        for root, dirs, files in os.walk("build", topdown=False):
            for file in files:
                if "__pycache__" in root:
                    continue
                if "entry.build" in root:  # exclude entry.build
                    continue
                all_files.append(
                    (p := os.path.join(root, file), p.replace("build", ""), file)
                )
        total_file = len(all_files)
        file_count = 0
        with zipfile.ZipFile(
                f"build\\{dist_file_name}", "w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            for p, arcname, file in all_files:
                zip_file.write(p, arcname=arcname)
                file_count += 1
                print(f"zip {file} ({file_count}) / ({total_file})")
        print(f"zip success: {dist_file_name}")
        print(
            "========================================================================="
        )
    # move archive to /build/release
    os.makedirs("build\\release", exist_ok=True)
    shutil.move(f"build\\{dist_file_name}", f"build\\release\\{dist_file_name}")
    print("move archive to /build/release")


def distribute(version: str, download_upx=False, p7zip=False, output=None):
    if os.path.exists("build"):
        shutil.rmtree("build")

    build_main_program(version)
    upx_files(get_upx(download_upx))
    # delete build\upx
    if download_upx:
        shutil.rmtree("build\\upx")

    # write run_with_args.bat and copy update_log.txt
    with open("build\\run_with_args.bat", "w", encoding="utf-8") as f:
        f.write(run_with_args_bat)
    shutil.copy("resources\\update_log.txt", "build\\update_log.txt")
    compress(version,output, p7zip=p7zip)


if __name__ == "__main__":
    """
    usage: python scripts/distribute.py -v 0.3.0 --download_upx --p7zip
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--version",
        type=str,
        help="version of this release",
    )
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default=None,
        help="output filename",
    )
    parser.add_argument(
        "--download_upx",
        action="store_true",
        help="download upx from github",
    )
    parser.add_argument(
        "--p7zip",
        action="store_true",
        help="zip with 7z",
    )
    args = parser.parse_args()

    ver = args.version
    if '/' in ver:
        ver = ver.split('/')[-1]

    if args.version:
        distribute(ver, args.download_upx, args.p7zip, args.output)

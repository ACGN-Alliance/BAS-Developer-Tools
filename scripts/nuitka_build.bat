@REM
python -m nuitka ^
    --standalone ^
    --lto=no ^
    --output-dir=build ^
    --company-name="ACGN-Alliance" ^
    --product-name="BlueArchive-Starter-Develop-Tools" ^
    --windows-icon-from-ico=bas.ico ^
    --file-version="0.2.4" ^
    --product-version="0.2.4" ^
    --windows-file-description="Develop Tools for BAS" ^
    --copyright="Copyright @ACGN-Alliance. All right reserved." ^
    --remove-output ^
    --include-module=OpenGL ^
    --include-package-data=OpenGL ^
    --nofollow-import-to=multiprocessing,viztracer,numpy,cv2 ^
    --windows-disable-console ^
    --msvc=latest ^
    --clang ^
    --enable-plugin=pyside6 ^
    --include-data-file=scrcpy/scrcpy-server.jar=scrcpy/scrcpy-server.jar ^
    entry.py
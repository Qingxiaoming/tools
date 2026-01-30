@echo off
REM Video Toolbox - build exe (ASCII only to avoid encoding issues)
echo [1/3] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller
) else (
    echo PyInstaller OK.
)

echo [2/3] Installing dependencies (mirror + long timeout)...
pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -q

echo [3/3] Building exe...
pyinstaller --noconfirm --clean video_tools.spec

if exist "dist\VideoTools.exe" (
    echo.
    echo Done. Output: dist\VideoTools.exe
    echo You can rename it to any name you like.
) else (
    echo.
    echo Build may have failed. Check errors above.
)
pause

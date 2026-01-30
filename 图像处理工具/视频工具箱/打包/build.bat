@echo off
chcp 65001 >nul
REM Video Toolbox - build exe
REM 双击运行此脚本即可，会自动切换到项目根目录

set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
cd /d "%ROOT%"

echo [1/3] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller
) else (
    echo PyInstaller OK.
)

echo [2/3] Installing dependencies...
pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -q

echo [3/3] Building exe...
cd "%SCRIPT_DIR%"
pyinstaller --noconfirm --clean video_tools.spec

if exist "dist\VideoTools.exe" (
    echo.
    echo Done. Output: 打包\dist\VideoTools.exe
    echo You can rename it to any name you like.
) else (
    echo.
    echo Build may have failed. Check errors above.
)
pause

chcp 65001 > nul
@echo off
title scrcpy + sndcpy

tasklist /FI "IMAGENAME eq scrcpy.exe" 2>nul | find /I /C "scrcpy.exe" >nul
if %errorlevel%==0 exit /b

:: Redmi手机编号
set SERIAL=3030725483000E2
::使其显示在副屏右上角
set /A X=2352
set /A Y=0
set /A W=648
set /A H=1440


:: 静默启动音频转发
::start "" /min "D:\scrcpy-win64-v3.3.1\sndcpy_auto.bat"

:: 投屏
scrcpy.exe -s %SERIAL% -K ^
  --no-audio ^
  --window-borderless ^
  --window-x %X% --window-y %Y% ^
  --window-width %W% --window-height %H% ^
  --always-on-top ^
  %HID_ARGS%
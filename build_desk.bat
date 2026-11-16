@echo off
rem ============================================================
rem   W I D G E T D E S K   -   build WidgetDesk.exe
rem   (this is NOT the dock and NOT the music widget)
rem ============================================================
cd /d "%~dp0"
title WidgetDesk build

for /f "tokens=2 delims==" %%v in ('findstr /b "VERSION" core\version.py') do set VER=%%v
set VER=%VER: =%
set VER=%VER:"=%
echo.
echo  ##############################################
echo  #   WIDGETDESK   version %VER%
echo  ##############################################
echo.

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo *** PyInstaller is not installed. Tell Claude - do NOT install anything yourself. ***
    goto :fail
)

echo [1/5] Closing running WidgetDesk.exe (if any)...
taskkill /f /im WidgetDesk.exe >nul 2>&1

set WORK=%TEMP%\WidgetDesk_build
if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%"

echo [2/5] Building (1-3 minutes)...
python -m PyInstaller --noconfirm --onefile --noconsole --name WidgetDesk --workpath "%WORK%\work" --distpath "%WORK%\dist" --specpath "%WORK%" "%~dp0desk.py"
if errorlevel 1 goto :fail
if not exist "%WORK%\dist\WidgetDesk.exe" goto :fail

echo [3/5] Copying to release\ ...
if not exist release mkdir release
if exist release\WidgetDesk.exe del /f /q release\WidgetDesk.exe
if exist release\WidgetDesk.exe (
    echo *** Cannot replace release\WidgetDesk.exe - the program is still running or the file is locked. ***
    goto :fail
)
copy /y "%WORK%\dist\WidgetDesk.exe" release\ >nul
if not exist release\WidgetDesk.exe goto :fail

echo [4/5] Checking that the new exe reports version %VER%...
del /f /q "%TEMP%\WidgetDesk_version.txt" >nul 2>&1
start "" /wait release\WidgetDesk.exe --version
set REP=
if exist "%TEMP%\WidgetDesk_version.txt" set /p REP=<"%TEMP%\WidgetDesk_version.txt"

echo [5/5] Writing release\build_info.txt ...
python tools\build_info.py release\WidgetDesk.exe "%REP%"
if errorlevel 1 (
    echo *** The built exe reports version "%REP%" but core\version.py says %VER%. ***
    goto :fail
)

color 2F
echo.
echo ============================================================
echo   DONE!  WidgetDesk %VER%
echo   File for GitHub Release (tag v%VER%):  release\WidgetDesk.exe
echo   Tell Claude: "gotovo" - Claude checks build_info.txt itself.
echo ============================================================
explorer release
pause
color
exit /b 0

:fail
color 4F
echo.
echo ************************************************************
echo   BUILD FAILED.  Make a screenshot of this window for Claude.
echo ************************************************************
pause
color
exit /b 1

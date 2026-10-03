@echo off
setlocal
cd /d "%~dp0"
echo.
echo xConfig Dart Renderer
echo =====================
echo Preparing source and generated dart assets...
where py >nul 2>nul
if %errorlevel%==0 (
  py scripts\restore_source_bundle.py
  if errorlevel 1 goto :error
  py scripts\author_assets.py
  if errorlevel 1 goto :error
  py scripts\web_player_assets.py
  if errorlevel 1 goto :error
  py scripts\build_catalog.py
  if errorlevel 1 goto :error
) else (
  python scripts\restore_source_bundle.py
  if errorlevel 1 goto :error
  python scripts\author_assets.py
  if errorlevel 1 goto :error
  python scripts\web_player_assets.py
  if errorlevel 1 goto :error
  python scripts\build_catalog.py
  if errorlevel 1 goto :error
)
echo Browser: http://localhost:4173/
echo For fully local Three.js: npm install
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:4173/"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m http.server 4173
) else (
  python -m http.server 4173
)
if errorlevel 1 pause
exit /b 0

:error
echo Asset preparation failed.
pause
exit /b 1

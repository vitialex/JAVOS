@echo off
title Compilador de JAVOS (.exe Standalone)
cd /d "%~dp0"

echo ==========================================================
echo        Compilando JAVOS a Ejecutable .exe para Windows
echo ==========================================================
echo.

echo [1/3] Verificando e instalando dependencias...
python -m pip install pyinstaller requests

echo.
echo [2/3] Generando ejecutable standalone JAVOS.exe...
:: Se usa %%TEMP%% para carpetas intermedias para evitar bloqueos de OneDrive/SharePoint
python -m PyInstaller --noconsole --onefile --clean --workpath "%TEMP%\javos_build" --distpath "%TEMP%\javos_dist" --name JAVOS javos_gui.py

echo.
echo [3/3] Copiando JAVOS.exe al directorio principal...
if exist "%TEMP%\javos_dist\JAVOS.exe" (
    copy /Y "%TEMP%\javos_dist\JAVOS.exe" "JAVOS.exe"
    echo.
    echo ==========================================================
    echo   [EXITO] Se ha actualizado JAVOS.exe correctamente.
    echo   Ya se puede hacer doble clic en JAVOS.exe directamente.
    echo ==========================================================
) else (
    echo [ERROR] No se pudo generar JAVOS.exe. Revisa los mensajes anteriores.
)

pause

@echo off
title JAVOS Launcher
cd /d "%~dp0"

echo [JAVOS] Comprobando entorno de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se ha encontrado Python en el sistema.
    echo Por favor instala Python o ejecuta el archivo standalone JAVOS.exe.
    pause
    exit /b 1
)

echo [JAVOS] Iniciando interfaz grafica...
start "" pythonw javos_gui.py
if %errorlevel% neq 0 (
    python javos_gui.py
)
exit /b 0

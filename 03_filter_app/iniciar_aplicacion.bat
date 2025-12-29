@echo off
cd /d "%~dp0"
echo ===========================================
echo   INICIANDO APLICACION DE FILTRADO (Fase 3)
echo ===========================================
echo.
echo Cargando modulos...
python -m src.ui.app
echo.
echo Aplicacion cerrada.
pause

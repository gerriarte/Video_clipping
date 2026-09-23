@echo off
title Clip Studio
cd /d "%~dp0"

echo.
echo  =========================================
echo    Clip Studio - Iniciando...
echo  =========================================
echo.
echo  Abriendo en http://localhost:8501
echo  Presiona Ctrl+C para detener.
echo.

call .venv\Scripts\activate.bat
streamlit run app.py --server.headless false

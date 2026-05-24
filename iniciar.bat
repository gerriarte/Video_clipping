@echo off
title Fast Video Clipping
cd /d "D:\ABRA\Zumo\Ediciones"

echo.
echo  =========================================
echo    Fast Video Clipping - Iniciando...
echo  =========================================
echo.
echo  Abriendo en http://localhost:8501
echo  Presiona Ctrl+C para detener.
echo.

call .venv\Scripts\activate.bat
streamlit run app.py --server.headless false

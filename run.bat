@echo off
title Border Sentinel AI - Quick Launcher
cls
echo =================================================================
echo    BORDER SENTINEL AI // FULL-STACK SYSTEM LAUNCHER (SIH26187)
echo =================================================================
echo.

set PYTHON_EXE=python
if exist "backend\.venv\Scripts\python.exe" set PYTHON_EXE=backend\.venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PYTHON_EXE=.venv\Scripts\python.exe

echo Select an option to run:
echo   [1] Run EVERYTHING (Backend + Dashboard + Stage 4 CV Pipeline)
echo   [2] Run Backend + React Dashboard
echo   [3] Run Stage 4 CV Pipeline Only ("Yash Raj 1.mp4" vs "Yash Raj 2.mp4")
echo   [4] Run Full Test Suite (API + Low-Light + Tripwire Tests)
echo.
set /p opt="Enter choice [1-4] (default: 1): "
if "%opt%"=="" set opt=1

if "%opt%"=="1" goto run_all
if "%opt%"=="2" goto run_web
if "%opt%"=="3" goto run_cv
if "%opt%"=="4" goto run_test
goto run_all

:run_all
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1 -RunPipeline -BeforeVideo "Yash Raj 1.mp4" -AfterVideo "Yash Raj 2.mp4"
pause
exit /b

:run_web
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
pause
exit /b

:run_cv
%PYTHON_EXE% step4_classifier_alerts.py "Yash Raj 1.mp4" "Yash Raj 2.mp4"
pause
exit /b

:run_test
echo --- Running Backend API Tests ---
%PYTHON_EXE% backend/test_api.py
echo.
echo --- Running Feature 1 Low-Light Hysteresis Tests ---
%PYTHON_EXE% test_feature1_lowlight.py
echo.
echo --- Running Feature 2 Virtual Tripwire Tests ---
%PYTHON_EXE% test_feature2_tripwire.py
pause
exit /b

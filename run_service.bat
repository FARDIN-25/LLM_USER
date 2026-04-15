@echo off
echo Starting LLM User Service in Python 3.12 Virtual Environment...
set "VENV_PATH=%~dp0venv"

if not exist "%VENV_PATH%\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run environment setup first.
    pause
    exit /b 1
)

echo [INFO] Activating venv and starting server...
call "%VENV_PATH%\Scripts\activate.bat"
python run.py
pause

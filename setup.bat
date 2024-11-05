@echo off
setlocal

:: Check Python version
python -c "import sys; ver = sys.version_info; exit(1 if ver.major != 3 or ver.minor > 12 else 0)" 2>nul
if errorlevel 1 (
    echo Python version detected is not compatible. Python 3.12 or lower is required.
    echo If you have multiple versions of Python installed, you can set the correct one by adjusting your PATH.
    exit /b 1
)

:: Create virtual environment
python -m venv .venv

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Upgrade pip
python -m pip install --upgrade pip

:: Install required packages
pip install -r dev-requirements.txt
pip install pywin32 pyautogui pillow

:: Install pre-commit hooks
pre-commit install

echo Setup completed successfully!
endlocal
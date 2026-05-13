@echo off
chcp 65001 >nul
echo ============================================
echo   Image Drawer - Build Standalone EXE
echo ============================================
echo.

echo [1/2] Installing PyInstaller...
pip install pyinstaller -q -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo [2/2] Building application...
python -m PyInstaller --clean build.spec
if %errorlevel% neq 0 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo.
echo   Launch:    dist\ImageDrawer\ImageDrawer.exe  (fast startup^)
echo.
echo   For distribution, zip the entire dist\ImageDrawer\ folder.
echo ============================================
pause
@echo off
chcp 65001 >nul
title 安装右键菜单 - 本地压缩解压工具

:: 以管理员权限运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process cmd -ArgumentList '/c ""%~f0""' -Verb RunAs"
    exit /b
)

echo ========================================
echo   本地压缩解压工具 - 右键菜单安装
echo ========================================
echo.

:: 获取脚本所在目录（main.py所在目录）
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "MAIN_PY=%SCRIPT_DIR%\main.py"

if not exist "%MAIN_PY%" (
    echo [错误] 找不到 main.py：%MAIN_PY%
    echo 请将本脚本放在 main.py 同目录下运行。
    pause
    exit /b 1
)

:: 查找 pythonw.exe（无控制台窗口）
set "PYTHONW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    set "PYTHONW=%%i"
    goto :found_pythonw
)
:found_pythonw

if "%PYTHONW%"=="" (
    echo [警告] 未找到 pythonw.exe，将使用 python.exe（会闪现黑色窗口）
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set "PYTHONW=%%i"
        goto :found_python
    )
    :found_python
)

if "%PYTHONW%"=="" (
    echo [错误] 未找到 Python，请先安装 Python 并加入 PATH。
    pause
    exit /b 1
)

echo [信息] Python: %PYTHONW%
echo [信息] 主程序: %MAIN_PY%
echo.

:: 构造调用命令（用 pythonw 避免黑窗）
set "COMPRESS_CMD=\"%PYTHONW%\" \"%MAIN_PY%\" --compress \"%%1\""
set "EXTRACT_CMD=\"%PYTHONW%\" \"%MAIN_PY%\" --extract \"%%1\""

echo 正在注册右键菜单...
echo.

:: ========== 1. 文件夹右键 → 压缩 ==========
reg add "HKCR\Directory\shell\CompressTool" /ve /d "压缩到..." /f >nul
reg add "HKCR\Directory\shell\CompressTool" /v "Icon" /d "%PYTHONW%" /f >nul
reg add "HKCR\Directory\shell\CompressTool\command" /ve /d "\"%PYTHONW%\" \"%MAIN_PY%\" --compress \"%%1\"" /f >nul
echo   [OK] 文件夹右键 → 压缩到...

:: ========== 2. 压缩包文件右键 → 解压 ==========
:: 为每种常见压缩扩展名注册解压菜单
set "EXTS=.zip .7z .rar .tar .gz .bz2 .xz .iso .cab .lzma .zstd .tgz .tar.gz"

for %%E in (%EXTS%) do (
    reg add "HKCR\%%E\shell\CompressToolExtract" /ve /d "解压到当前文件夹" /f >nul 2>&1
    reg add "HKCR\%%E\shell\CompressToolExtract\command" /ve /d "\"%PYTHONW%\" \"%MAIN_PY%\" --extract \"%%1\"" /f >nul 2>&1
)

:: 同时在 SystemFileAssociations 下注册（更可靠，覆盖更多文件类型关联）
for %%E in (.zip .7z .rar .tar .gz .bz2 .xz .iso .cab .lzma .zstd .tgz) do (
    reg add "HKCR\SystemFileAssociations\%%E\shell\CompressToolExtract" /ve /d "解压到当前文件夹" /f >nul 2>&1
    reg add "HKCR\SystemFileAssociations\%%E\shell\CompressToolExtract\command" /ve /d "\"%PYTHONW%\" \"%MAIN_PY%\" --extract \"%%1\"" /f >nul 2>&1
)

echo   [OK] 压缩包右键 → 解压到当前文件夹
echo.

:: 刷新资源管理器
echo 正在刷新资源管理器...
taskkill /f /im explorer.exe >nul 2>&1
start explorer.exe

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 右键菜单已添加：
echo   - 右键任意文件夹 → "压缩到..."
echo   - 右键压缩包(zip/7z/rar等) → "解压到当前文件夹"
echo.
echo 如需卸载，请运行 uninstall_menu.bat
echo.
pause

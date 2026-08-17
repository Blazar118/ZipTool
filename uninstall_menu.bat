@echo off
chcp 65001 >nul
title 卸载右键菜单 - 本地压缩解压工具

:: 以管理员权限运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process cmd -ArgumentList '/c ""%~f0""' -Verb RunAs"
    exit /b
)

echo ========================================
echo   本地压缩解压工具 - 右键菜单卸载
echo ========================================
echo.

echo 正在移除右键菜单...
echo.

:: 移除文件夹右键压缩菜单
reg delete "HKCR\Directory\shell\CompressTool" /f >nul 2>&1
echo   [OK] 移除文件夹右键压缩菜单

:: 移除压缩包扩展名右键解压菜单
set "EXTS=.zip .7z .rar .tar .gz .bz2 .xz .iso .cab .lzma .zstd .tgz"

for %%E in (%EXTS%) do (
    reg delete "HKCR\%%E\shell\CompressToolExtract" /f >nul 2>&1
    reg delete "HKCR\SystemFileAssociations\%%E\shell\CompressToolExtract" /f >nul 2>&1
)
echo   [OK] 移除压缩包右键解压菜单

:: 刷新资源管理器
echo.
echo 正在刷新资源管理器...
taskkill /f /im explorer.exe >nul 2>&1
start explorer.exe

echo.
echo ========================================
echo   卸载完成！
echo ========================================
echo.
pause

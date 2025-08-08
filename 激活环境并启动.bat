@echo off
chcp 65001 >nul
title BCI SSVEP 实验管理器
cls
echo.
echo ================================================
echo            BCI SSVEP 实验管理器
echo ================================================
echo.

cd /d C:\Users\23842\Desktop\bci
echo 当前目录: %CD%

echo.
echo 正在查找 conda 安装...

rem 设置可能的conda路径
set "CONDA_FOUND=0"
set "CONDA_PATH="

rem 检查常见的conda安装位置
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "CONDA_PATH=%USERPROFILE%\miniconda3"
    set "CONDA_FOUND=1"
    echo 找到 miniconda3: %CONDA_PATH%
    goto :activate_env
)

if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "CONDA_PATH=%USERPROFILE%\anaconda3"
    set "CONDA_FOUND=1"
    echo 找到 anaconda3: %CONDA_PATH%
    goto :activate_env
)

if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
    set "CONDA_PATH=C:\ProgramData\miniconda3"
    set "CONDA_FOUND=1"
    echo 找到系统 miniconda3: %CONDA_PATH%
    goto :activate_env
)

if exist "C:\ProgramData\anaconda3\Scripts\conda.exe" (
    set "CONDA_PATH=C:\ProgramData\anaconda3"
    set "CONDA_FOUND=1"
    echo 找到系统 anaconda3: %CONDA_PATH%
    goto :activate_env
)

rem 如果没找到conda
echo.
echo 未找到 conda 安装，尝试使用当前 Python 环境
echo 注意: 可能缺少某些依赖包
echo.
goto :direct_start

:activate_env
echo.
echo 激活 bci-ssvep 环境...

rem 初始化conda
call "%CONDA_PATH%\Scripts\activate.bat" "%CONDA_PATH%"

rem 激活目标环境
call "%CONDA_PATH%\Scripts\activate.bat" bci-ssvep 2>nul

if errorlevel 1 (
    echo.
    echo 警告: 无法激活 bci-ssvep 环境
    echo 可能的原因:
    echo 1. 环境不存在
    echo 2. 环境名称错误
    echo.
    echo 继续使用 base 环境...
) else (
    echo 成功激活 bci-ssvep 环境
)

goto :start_gui

:direct_start
echo 使用当前 Python 环境直接启动...

:start_gui
echo.
echo 检查依赖包...
python -c "import pygame, pylsl, scipy, tkinter; print('所有依赖包正常')" 2>nul
if errorlevel 1 (
    echo.
    echo 警告: 缺少某些依赖包
    echo 请确保已安装: pygame pylsl scipy scikit-learn
    echo.
    choice /c YN /m "是否继续运行"
    if errorlevel 2 exit /b 1
)

echo.
echo 启动GUI界面...
python gui\runner.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查:
    echo 1. Python 环境
    echo 2. 依赖包安装
    echo 3. 文件路径
)

echo.
echo ================================================
echo            程序已退出
echo ================================================
pause

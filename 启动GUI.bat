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
echo 激活 Anaconda 环境...

rem 使用找到的anaconda3路径
set "CONDA_PATH=%USERPROFILE%\anaconda3"

rem 检查anaconda3是否存在
if not exist "%CONDA_PATH%\Scripts\conda.exe" (
    echo 错误: 找不到 Anaconda 安装
    echo 路径: %CONDA_PATH%
    pause
    exit /b 1
)

echo 找到 Anaconda: %CONDA_PATH%

rem 初始化conda环境
call "%CONDA_PATH%\Scripts\activate.bat" "%CONDA_PATH%"

rem 激活bci-ssvep环境
echo 激活 bci-ssvep 环境...
call conda activate bci-ssvep

if errorlevel 1 (
    echo.
    echo 警告: 无法激活 bci-ssvep 环境
    echo 请检查环境是否存在: conda env list
    echo.
    echo 继续使用当前环境...
) else (
    echo 成功激活 bci-ssvep 环境
)

echo.
echo 检查关键依赖包...
python -c "import pygame; print('pygame: OK')" 2>nul || echo "pygame: 缺失"
python -c "import pylsl; print('pylsl: OK')" 2>nul || echo "pylsl: 缺失"
python -c "import scipy; print('scipy: OK')" 2>nul || echo "scipy: 缺失"
python -c "import tkinter; print('tkinter: OK')" 2>nul || echo "tkinter: 缺失"

echo.
echo 启动GUI界面...
python gui\runner.py

echo.
echo ================================================
echo            程序已退出
echo ================================================
pause
@echo off
chcp 65001 >nul
title BCI SSVEP 实验管理器
echo.
echo ===============================================
echo           BCI SSVEP 实验管理器
echo ===============================================
echo.
echo 正在激活 conda 环境...

rem 激活conda环境
call "%USERPROFILE%\miniconda3\Scripts\activate.bat" bci-ssvep 2>nul
if errorlevel 1 (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" bci-ssvep 2>nul
    if errorlevel 1 (
        call conda activate bci-ssvep 2>nul
        if errorlevel 1 (
            echo 错误: 无法激活 bci-ssvep 环境
            echo 请手动激活环境后重试：conda activate bci-ssvep
            pause
            exit /b 1
        )
    )
)

echo conda 环境已激活
echo 切换到工作目录...
cd /d C:\Users\23842\Desktop\bci

if not exist "gui\runner.py" (
    echo 错误: 找不到 GUI 文件
    echo 当前目录: %CD%
    pause
    exit /b 1
)

echo 启动GUI界面...
python gui\runner.py

echo.
echo GUI 已关闭
pause
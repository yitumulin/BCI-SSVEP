@echo off
chcp 65001 >nul
title BCI SSVEP 实验管理器
cls
echo.
echo ===============================================
echo           BCI SSVEP 实验管理器
echo ===============================================
echo.
echo 正在检查环境...

rem 尝试多种方式激活conda环境
echo 尝试激活 bci-ssvep 环境...

rem 方法1: 通过用户目录的conda
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    echo 找到 miniconda3，正在激活...
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" bci-ssvep
    goto :check_env
)

if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    echo 找到 anaconda3，正在激活...
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" bci-ssvep
    goto :check_env
)

rem 方法2: 通过PATH中的conda
echo 尝试通过 PATH 激活 conda...
call conda activate bci-ssvep 2>nul
if not errorlevel 1 goto :check_env

rem 如果都失败了
echo.
echo 警告: 无法自动激活 bci-ssvep 环境
echo 请确保：
echo 1. 已安装 Anaconda 或 Miniconda
echo 2. 已创建 bci-ssvep 环境
echo 3. 在环境中安装了所需的包
echo.
echo 继续启动程序...

:check_env
echo.
echo 环境检查完成，启动GUI...
cd /d C:\Users\23842\Desktop\bci

if not exist "gui\runner.py" (
    echo.
    echo 错误: 找不到 GUI 文件
    echo 当前目录: %CD%
    echo 请确保在正确的目录中运行此程序
    echo.
    pause
    exit /b 1
)

python gui\runner.py

echo.
echo ===============================================
echo           程序已退出
echo ===============================================
pause
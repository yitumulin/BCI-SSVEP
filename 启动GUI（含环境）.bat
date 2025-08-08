@echo off
chcp 65001 >nul
title BCI SSVEP 实验管理器
cls
echo.
echo ================================================
echo            BCI SSVEP 实验管理器
echo ================================================
echo.

rem 切换到正确目录
cd /d C:\Users\23842\Desktop\bci
echo 当前目录: %CD%

rem 检查文件是否存在
if not exist "gui\runner.py" (
    echo.
    echo 错误: 找不到 gui\runner.py 文件
    pause
    exit /b 1
)

echo.
echo 尝试激活 bci-ssvep conda 环境...

rem 尝试不同的conda激活方式
set "CONDA_ACTIVATED=0"

rem 方法1: 通过conda activate
call conda activate bci-ssvep 2>nul
if not errorlevel 1 (
    echo 成功激活 bci-ssvep 环境 ^(方法1^)
    set "CONDA_ACTIVATED=1"
    goto :start_gui
)

rem 方法2: 尝试miniconda路径
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" bci-ssvep 2>nul
    if not errorlevel 1 (
        echo 成功激活 bci-ssvep 环境 ^(方法2^)
        set "CONDA_ACTIVATED=1"
        goto :start_gui
    )
)

rem 方法3: 尝试anaconda路径
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" bci-ssvep 2>nul
    if not errorlevel 1 (
        echo 成功激活 bci-ssvep 环境 ^(方法3^)
        set "CONDA_ACTIVATED=1"
        goto :start_gui
    )
)

rem 如果都失败了
echo.
echo 警告: 无法自动激活 bci-ssvep 环境
echo 请手动激活环境后重新运行:
echo   conda activate bci-ssvep
echo   python gui\runner.py
echo.
echo 或者尝试继续运行 ^(可能缺少某些依赖^)
choice /c YN /m "是否继续运行"
if errorlevel 2 exit /b 1

:start_gui
echo.
echo 启动GUI界面...
echo.

python gui\runner.py

if errorlevel 1 (
    echo.
    echo 启动失败，可能的原因:
    echo 1. conda环境未正确激活
    echo 2. 缺少依赖包 ^(pygame, pylsl, scipy等^)
    echo 3. Python环境问题
    echo.
    echo 建议检查环境:
    echo   conda list pygame
    echo   conda list pylsl
)

echo.
echo ================================================
echo            程序已退出
echo ================================================
pause

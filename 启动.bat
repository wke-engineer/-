@echo off
chcp 65001 >nul
REM ============================================================
REM  星海日记 —— 一键启动（Windows）
REM  双击本文件即可启动，会自动装依赖 + 建表 + 打开浏览器
REM ============================================================

setlocal
cd /d "%~dp0"

REM ---- 找一个可用的 Python ----
set PY=
if exist "C:\Users\wangl\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
    set PY=C:\Users\wangl\.workbuddy\binaries\python\envs\default\Scripts\python.exe
) else (
    where python >nul 2>nul && set PY=python
)

if "%PY%"=="" (
    echo [错误] 没有找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo 使用 Python: %PY%
echo.

REM ---- 检查依赖，缺了就装 ----
REM 用国内镜像源，否则直连 pypi.org 可能非常慢
set MIRROR=-i https://mirrors.cloud.tencent.com/pypi/simple/ --trusted-host mirrors.cloud.tencent.com

"%PY%" -c "import streamlit, sqlalchemy" 2>nul
if errorlevel 1 (
    echo [1/3] 正在安装依赖，第一次会慢一点...
    "%PY%" -m pip install %MIRROR% -r requirements.txt
) else (
    echo [1/3] 依赖已就绪
)

REM ---- 初始化数据库（建表 + 演示数据，幂等可重复执行）----
echo [2/3] 初始化数据库...
"%PY%" scripts\init_db.py --demo

REM ---- 启动 ----
echo [3/3] 启动星海日记...
echo.
"%PY%" -m streamlit run app.py

endlocal
pause

@echo off
chcp 65001 >nul
REM ============================================================
REM  星海日记 —— 一键推送到 GitHub
REM
REM  使用前只需做一件事：
REM      在浏览器打开 https://github.com/new
REM      仓库名填 xinghai-diary
REM      私有/公开随你，但【不要】勾选 Add README / .gitignore / license
REM      点 Create repository
REM  然后双击本文件即可。
REM ============================================================

setlocal
cd /d "%~dp0"

set REPO_USER=wke-engineer
set REPO_NAME=xinghai-diary
set REPO_URL=git@github.com:%REPO_USER%/%REPO_NAME%.git

echo ============================================================
echo   目标仓库: %REPO_URL%
echo ============================================================
echo.

REM ---- 1. 检查 git ----
where git >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 git，请先安装 Git
    pause
    exit /b 1
)

REM ---- 2. 检查是否还没提交 ----
git rev-parse HEAD >nul 2>nul
if errorlevel 1 (
    echo [错误] 本地还没有任何提交，请先 git add + git commit
    pause
    exit /b 1
)

REM ---- 3. 配置远程地址（可重复执行，先删后加避免重复）----
git remote remove origin >nul 2>nul
git remote add origin %REPO_URL%
git branch -M main

echo [1/3] 测试到 GitHub 的 SSH 连通性...
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -T git@github.com 2>&1 | findstr /C:"successfully authenticated" >nul
if errorlevel 1 (
    echo.
    echo [警告] SSH 认证未通过。可能的原因：
    echo        1) 还没把公钥加到 GitHub（Settings - SSH and GPG keys）
    echo        2) 22 端口被网络封了 —— 解决办法见 README「推送排障」
    echo.
    echo        当前公钥内容：
    type "%USERPROFILE%\.ssh\id_ed25519.pub" 2>nul
    echo.
    set /p GO="仍要继续尝试推送吗？(y/N) "
    if /i not "%GO%"=="y" exit /b 1
) else (
    echo        SSH 认证通过
)

echo.
echo [2/3] 检查远程仓库是否存在...
git ls-remote --exit-code origin >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 读不到远程仓库。请确认：
    echo        - 已经在 https://github.com/new 创建了名为 %REPO_NAME% 的空仓库
    echo        - 仓库属于账号 %REPO_USER%
    echo.
    pause
    exit /b 1
)
echo        远程仓库可访问

echo.
echo [3/3] 推送 main 分支...
git push -u origin main
if errorlevel 1 (
    echo.
    echo [失败] 推送出错，请把上面的报错发出来
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   推送完成！
echo   https://github.com/%REPO_USER%/%REPO_NAME%
echo ============================================================
echo.
pause
endlocal

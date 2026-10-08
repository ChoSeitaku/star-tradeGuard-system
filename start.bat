@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   电商风险控制系统 star-tradeGuard  启动脚本
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv
    echo        请先执行：python -m venv .venv
    echo        并安装依赖：.venv\Scripts\python.exe -m pip install fastapi uvicorn
    pause
    exit /b 1
)

if not exist "data\tradeguard.db" (
    echo [1/3] 未检测到数据库，正在初始化建表与示例数据...
    ".venv\Scripts\python.exe" scripts\init_db.py
    if errorlevel 1 (
        echo [错误] 数据库初始化失败
        pause
        exit /b 1
    )
) else (
    echo [1/3] 数据库已存在，跳过初始化
    echo        如需重置数据请执行：.venv\Scripts\python.exe scripts\init_db.py --force
)

if not exist "frontend\dist\index.html" (
    echo [2/3] 警告：未找到前端构建产物 frontend\dist
    echo        本次仅启动后端接口，可访问 http://127.0.0.1:8005/docs 查看接口文档
    echo        如需界面请执行：cd frontend ^&^& npm install ^&^& npm run build
) else (
    echo [2/3] 前端构建产物已就绪
)

echo [3/3] 正在启动服务...
echo.
echo    系统首页：http://127.0.0.1:8005
echo    接口文档：http://127.0.0.1:8005/docs
echo.
echo    按 Ctrl+C 停止服务
echo ============================================================
echo.

".venv\Scripts\python.exe" -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8005

pause

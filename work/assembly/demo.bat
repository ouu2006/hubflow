@echo off
chcp 65001 >nul
rem demo.bat - 一键演示入口，双击即跑（不许要求现场敲命令、不许要求现场装东西）。
rem 骨架阶段（Issue #40）：先跑 run_all.py --dry-run 做自检；业务模块接入后
rem 由 run_all.py 串起 孪生 -> 感知判级 -> 决策 -> 快照 -> 接口层 -> 管理端。
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [demo] 未找到 python，请先安装 Python 3.11+ 并加入 PATH。
  pause
  exit /b 1
)

python run_all.py --dry-run %*
if errorlevel 1 (
  echo [demo] 自检未通过，请看上方输出；运行产物与日志在 out\ 与 logs\。
) else (
  echo [demo] 自检通过。
)
pause

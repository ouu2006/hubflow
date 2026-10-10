#!/usr/bin/env bash
# WSL 侧构建复跑(总控 §4 WSL 工作模式:代码经 /mnt/e 直达,构建产物放 ext4,
# 不污染 Windows 侧 node_modules/dist)。用法(Windows 侧):
#   wsl.exe -d <发行版> -- bash /mnt/e/.../harness-core/ui-vue/scripts/wsl-build.sh
set -eu
REPO=/mnt/e/develop/project_files/project/ict-project/harness-core/ui-vue
export HOME="${HOME:-/root}"
[ -d "$HOME" ] || HOME=$(getent passwd "$(id -u)" | cut -d: -f6)
DEST="$HOME/targets/ui-vue-wsl"
export PATH="$HOME/.local/bin:$PATH"

echo "== 环境 =="
echo "user=$(id -un) home=$HOME node=$(node --version) npm=$(npm --version)"

echo "== 同步源码(排除 node_modules/dist)-> $DEST =="
rm -rf "$DEST"
mkdir -p "$DEST"
cd "$REPO"
tar cf - --exclude=node_modules --exclude=dist . | tar xf - -C "$DEST"

echo "== npm ci =="
cd "$DEST"
npm ci --no-audit --no-fund >/dev/null

echo "== npm run build(vue-tsc -b && vite build)=="
npm run build 2>&1 | tail -8
echo "== WSL BUILD DONE =="

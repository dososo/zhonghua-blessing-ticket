#!/usr/bin/env bash
# 安装本地Skill，默认不联网、不启用额外权限、不覆盖旧目录。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '未找到Python3。可在Codex中读取README后请其将skills/zhonghua-blessing-ticket完整复制到~/.agents/skills/，无需安装Python包。' >&2
  exit 2
fi
exec python3 "$ROOT/scripts/install.py" "$@"

#!/usr/bin/env bash
# 在 Mac 上开一个手机大小的 Chrome 窗口看本地测试版：触控板双指滑动就是网页滚动，⌘⇧4 再按空格点窗口就能截图。
# iOS 模拟器要按住拖动才等于手指滑动，看效果、截图不方便；手机上的真实触摸、键盘还是要在模拟器或真机上看。
#
# 用法：tests/mobile/mac_preview.sh [se|iphone|promax] [路径]
#   se      375×667（iPhone SE）
#   iphone  390×844（默认，常见的 iPhone 尺寸）
#   promax  440×956（iPhone 17 Pro Max）
# 例：tests/mobile/mac_preview.sh se /learning-dashboard
# 要先在本机 3100 端口跑着前端（见 docs/core/测试文档.md「手机兼容性测试」）。
# 用单独的 Chrome 配置目录，不动平时用的 Chrome；关掉窗口即可。
set -euo pipefail

case "${1:-iphone}" in
  se) W=375 H=667 ;;
  iphone) W=390 H=844 ;;
  promax) W=440 H=956 ;;
  *) echo "尺寸只能是 se、iphone、promax" >&2; exit 1 ;;
esac
URL="${BASE_URL:-http://localhost:3100}${2:-/}"
PROFILE="${TMPDIR:-/tmp}/word-learning-phone-preview"

curl -s -o /dev/null --max-time 3 "$URL" || { echo "打不开 $URL：本地前端没在跑？" >&2; exit 1; }
# 窗口高度含标题栏（约 28px），网页区域按手机屏幕的宽高
open -na "Google Chrome" --args --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
  --app="$URL" --window-size="$W,$((H + 28))" --window-position=80,40
echo "已打开 ${W}×${H} 的窗口：$URL"

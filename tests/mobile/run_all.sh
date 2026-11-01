#!/bin/bash
# 三台手机同时走一遍学新词流程：两台 iOS 模拟器（小屏、大屏）+ 安卓模拟器。
#   tests/mobile/run_all.sh          功能走查（walk.py）
#   tests/mobile/run_all.sh audit    版面检查（audit.py）：每页每个状态截图、量版面和美学指标，汇总成 .review/layout/报告.md
# 前置准备与人工检查项见 docs/core/测试文档.md「手机兼容性测试」，检查标准和记录见 docs/core/界面检查记录.md。
#   IOS_DEVICES   iOS 模拟器名字，逗号分隔（默认 "WL iPhone SE,iPhone 17 Pro Max"）
#   ANDROID_PYTHON  装了 playwright 的 Python（默认 python3）
#   BASE_URL      前端地址（默认 http://localhost:3100）；MOBILE_OUT 截图和日志目录（默认 .review/mobile）
set -u
cd "$(dirname "$0")/../.."
BASE_URL=${BASE_URL:-http://localhost:3100}
MODE=${1:-walk}
if [ "$MODE" = audit ]; then OUT=${MOBILE_OUT:-.review/layout}; else OUT=${MOBILE_OUT:-.review/mobile}; fi
IOS_DEVICES=${IOS_DEVICES:-WL iPhone SE,iPhone 17 Pro Max}
ANDROID_PYTHON=${ANDROID_PYTHON:-python3}
ADB=${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}
mkdir -p "$OUT"
export BASE_URL MOBILE_OUT=$OUT

# 前端要在 npm run build 完成之后启动，否则旧进程拿着构建前的文件表，新样式表 404，页面成了裸 HTML
css=$(curl -s "$BASE_URL/learning-dashboard" | grep -o '/_next/static/css/[^"]*\.css' | head -1)
if [ -z "$css" ] || [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$css")" != 200 ]; then
  echo "前端 $BASE_URL 的样式表取不到：先 npm run build，再重启 next start" >&2
  exit 1
fi

pids=() names=() started=()
port=4723
IFS=',' read -ra devices <<< "$IOS_DEVICES"
for device in "${devices[@]}"; do
  udid=$(xcrun simctl list devices available -j | python3 -c "import json, sys
for ds in json.load(sys.stdin)['devices'].values():
    for d in ds:
        if d['name'] == sys.argv[1]: print(d['udid']); sys.exit()" "$device")
  if [ -z "$udid" ]; then echo "没有名为 $device 的 iOS 模拟器" >&2; exit 1; fi
  xcrun simctl boot "$udid" 2>/dev/null
  # 一个 safaridriver 同时只带一台模拟器，每台各开一个端口
  if ! curl -s "localhost:$port/status" >/dev/null; then
    /usr/bin/safaridriver -p "$port" & started+=($!)
    sleep 2
  fi
  name=$(echo "$device" | tr 'A-Z ' 'a-z-')
  WD_PORT=$port python3 tests/mobile/$MODE.py ios "$udid" "$name" > "$OUT/$name.log" 2>&1 & pids+=($!) names+=("$name")
  port=$((port + 1))
done

if "$ADB" get-state >/dev/null 2>&1; then
  # Chrome 跳过首次运行引导；冷启动后才会开 DevTools 接口。localhost 经 adb reverse 回到本机，
  # 和线上 https 一样算安全来源（10.0.2.2 不算，装不成主屏应用）
  "$ADB" shell am set-debug-app --persistent com.android.chrome >/dev/null
  "$ADB" shell 'echo "_ --disable-fre --no-default-browser-check --no-first-run" > /data/local/tmp/chrome-command-line'
  "$ADB" shell am force-stop com.android.chrome
  "$ADB" reverse tcp:${BASE_URL##*:} tcp:${BASE_URL##*:} >/dev/null
  # 只冷启动 Chrome、不开网页：测试脚本自己开标签页、跑完关掉（开网页的话每跑一次多一个标签页）
  "$ADB" shell monkey -p com.android.chrome -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  for _ in $(seq 10); do "$ADB" shell cat /proc/net/unix | grep -q chrome_devtools_remote && break; sleep 1; done
  "$ADB" forward tcp:9333 localabstract:chrome_devtools_remote >/dev/null
  "$ANDROID_PYTHON" tests/mobile/$MODE.py android android > "$OUT/android.log" 2>&1 & pids+=($!) names+=(android)
else
  echo "没有连着的安卓模拟器，跳过安卓" >&2
fi

failed=0
for i in ${pids[@]+"${!pids[@]}"}; do
  wait "${pids[$i]}" || failed=1
  grep -E 'FAIL|ERROR|passed' "$OUT/${names[$i]}.log"
done
for pid in ${started[@]+"${started[@]}"}; do kill "$pid" 2>/dev/null; done
[ "$MODE" = audit ] && python3 tests/mobile/audit.py report
echo "截图和日志：$OUT"
exit $failed

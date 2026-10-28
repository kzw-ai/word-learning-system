#!/bin/bash
# 本地开发一键启动：后端（5004）+ 前端开发服务器（3000）。
# 生产环境由 PM2 管理（见 CLAUDE.md），不要在服务器上用这个脚本。

cd "$(dirname "$0")"
echo "🚀 启动自适应学习系统（本地开发）..."
echo "=================================="

# 后端首次启动会自动建表、写入示范数据、导入论文练习题并修复素材，
# 不需要单独跑种子脚本。ALLOW_USER_ID_PARAM=1 让右下角的 UserSwitcher
# 能切换测试用户——只用于本地，生产环境绝不能设置。
echo "🔧 启动后端 (端口 5004)..."
ALLOW_USER_ID_PARAM=1 python3 app_phase.py &
API_PID=$!

echo "🎨 启动前端开发服务器 (端口 3000)..."
npm run dev &
WEB_PID=$!

trap 'kill $API_PID $WEB_PID 2>/dev/null' INT TERM EXIT

for i in $(seq 1 30); do
    curl -s http://localhost:5004/api/stats > /dev/null 2>&1 && break
    sleep 1
done
if curl -s http://localhost:5004/api/stats > /dev/null 2>&1; then
    echo "✅ 后端已就绪"
else
    echo "⚠️  后端未响应，请查看上方日志"
fi

echo ""
echo "🌐 访问地址:"
echo "   主页:           http://localhost:3000/"
echo "   学习看板:       http://localhost:3000/learning-dashboard"
echo "   今日复习:       http://localhost:3000/today-review"
echo ""
echo "📚 词库为空时导入论文学习素材："
echo "   python3 scripts/import_learning_materials.py"
echo ""
echo "按 Ctrl+C 停止前后端..."
wait

# Word Learning System — 项目指令 (Claude Code Custom Instructions)

## 项目概述

这是一个面向中文作为外语 (CFL) 学习者的**自适应词汇学习系统**，源自北京大学硕士论文研究。
前端使用 Next.js + React + TypeScript + Tailwind CSS，后端使用 Python Flask，通过 Nginx 反向代理对外暴露。

## 运行架构

### ⚠️ 重要：所有服务通过 PM2 管理，不要手动启动 python3 或 node 进程！

| 服务 | PM2 名称 | 端口 | 启动命令 | 说明 |
|------|----------|------|----------|------|
| 前端 | `learn-frontend` | 3002 (内部) | `npm start -- -p 3002` | Next.js 生产模式 |
| 后端 | `learn-backend` | 5004 | `python3 app_phase.py` | Flask API 服务 |

### 常用操作
```bash
# 查看服务状态
pm2 list

# 重启前端（改代码后需要先 npm run build）
cd "/home/coder/word learning system" && npm run build && pm2 restart learn-frontend

# 重启后端
pm2 restart learn-backend

# 查看日志
pm2 logs learn-frontend --lines 50
pm2 logs learn-backend --lines 50
```

### Nginx 反向代理配置
- 配置文件：`/etc/nginx/conf.d/learn.conf`
- 域名：`learnchinese.kzwbelieve.top`（支持 HTTPS）
- `/api/` → 转发至 Flask 后端 (5004)
- `^/(words|word)(/|$)` → 转发至 Flask 后端 (5004)
- `/` → 其余请求转发至 Next.js 前端 (3002)

### 端口说明
- **3002**：Next.js 前端（PM2 管理）
- **5004**：Flask 后端（PM2 管理）
- **3000, 3001**：未使用，访问会 Connection Refused，这是**正常的**
- **80/443**：Nginx 对外端口

## 已知的正常警告（不需要修复）

### ⚠️ `自适应引擎模块未找到，将使用简化版本`
这是后端启动时的**预期行为**。完整的自适应推荐引擎尚未集成，代码中设计了 fallback 机制使用简化版本。
此警告**不是 Bug，不要尝试修复**。

### ⚠️ `Browserslist: browsers data is X months old`
这是 Next.js 构建时的兼容性数据提示，不影响构建结果。可忽略。

## 项目结构

```
word learning system/
├── pages/                          # Next.js 页面
│   ├── word-learning-entrance.tsx  # VKS 入口页（词汇知识量表选择）
│   ├── character-learning.tsx      # 字学习模块
│   ├── word-learning.tsx           # 词学习模块
│   ├── collocation-learning.tsx    # 搭配学习模块
│   ├── sentence-learning.tsx       # 例句学习模块
│   ├── exercise.tsx                # 练习/测验模块
│   ├── learning-dashboard.tsx      # 学习看板
│   └── today-review.tsx            # 今日复习
├── src/
│   ├── context/                    # React Context (LearningContext, LearningSessionContext)
│   ├── hooks/                      # 自定义 hooks (useLearningNavigation)
│   └── lib/                        # 工具库 (apiClient.ts)
├── hooks/                          # 追踪 hooks (useTimeTracking)
├── components/                     # UI 组件 (AudioPlayer, ReviewReminder 等)
├── app_phase.py                   # Flask 后端主入口
├── package.json                    # Node.js 依赖
└── CLAUDE.md                       # 本文件
```

## 开发规范

### 前端修改流程
1. 编辑 `pages/` 或 `components/` 下的文件
2. 运行 `npm run build` 构建生产包
3. 构建成功后运行 `pm2 restart learn-frontend`
4. **不要**运行 `npm run dev`，生产环境使用 `npm start`

### 后端修改流程
1. 编辑 `app_phase.py` 或相关 Python 文件
2. 运行 `pm2 restart learn-backend`

### 用户身份（不要在生产环境放开）
- 身份只认两种凭证：登录 session token，或未登录访客的 `guest_id` cookie（前端首次访问自动生成，见 `src/lib/guestIdentity.ts`）
- 请求里的 `user_id`（URL / query / body）**不是**身份。只有设置环境变量 `ALLOW_USER_ID_PARAM=1` 时才被接受，用于本地开发切换测试用户（右下角 UserSwitcher）和 pytest
- **生产环境的 PM2 进程绝不能设置 `ALLOW_USER_ID_PARAM`**——设了就等于任何人在请求里填别人的 `user_id` 即可读写对方数据

### UI/UX 设计约定
- 所有学习页面使用**响应式全屏布局**：手机全屏 (`h-[100dvh]`)，桌面居中限宽 (`max-w-[430px]`)
- 使用 `env(safe-area-inset-top)` 适配手机刘海/灵动岛
- 使用 `env(safe-area-inset-bottom)` 适配底部安全区
- 正文字体不低于 `text-sm` (14px)，标题使用 `text-xl` 或 `text-2xl`
- 按钮最小触控高度 `h-9` (36px)
- **不要**创建模拟手机框（device mockup），页面本身就是全屏的

### 不要做的事情
- ❌ 不要手动运行 `python3 app_phase.py` 或 `node` 启动服务
- ❌ 不要修改 `/etc/nginx/` 配置（除非明确被要求）
- ❌ 不要尝试"修复"自适应引擎警告
- ❌ 不要在 3001 端口寻找服务或尝试启动服务
- ❌ 不要安装全局系统包

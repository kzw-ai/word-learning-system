# 测试说明

## 📋 测试套件

| 文件 | 类型 | 测试内容 | 是否需要启动服务 |
|------|------|----------|------------------|
| `test_adaptive_engine.py` | pytest 单元测试 | 改良 SM-2 间隔计算、质量因子、ease factor、模块推荐规则、到期复习优先级 | 否（临时数据库） |
| `test_api.py` | pytest 集成测试 | 核心 API、易混淆词、会话追踪、自适应推荐、认证流程、用户数据隔离 | 否（Flask test client + 临时数据库） |
| `e2e/smoke.test.js` | E2E 冒烟测试 | 全部 19 个页面的渲染与运行时错误、老用户回访水合、首页入口与学习链路的页面跳转 | **是**（前端 :3000 + 后端 :5004） |
| `test_time_tracking.js` | 手动脚本 | 时间追踪 API 手动验证 | 是（后端 :5004） |
| `mobile/run_all.sh` | 手机兼容性测试 | iOS 模拟器 Safari（小屏、大屏）+ 安卓 Chrome 同时用真实触摸走一遍学新词，发布前必做；用法见 `docs/core/测试文档.md`「手机兼容性测试」 | **是**（前端 :3100 + 后端 :5004 + 模拟器） |

---

## 🚀 运行测试

### Python 测试（推荐日常使用，无需启动任何服务）

```bash
# 全部
npm test            # 等价于 python3 -m pytest tests -q

# 单独跑某个套件
python3 -m pytest tests/test_adaptive_engine.py -v
python3 -m pytest tests/test_api.py -v
```

测试通过 `WORDS_DB_PATH` 环境变量把数据库指向临时文件，**不会碰真实的
`words_extended.db`**。首次运行需要安装 pytest：`pip3 install pytest --user`。

### E2E 冒烟测试（改动 UI 后运行）

```bash
# 1. 启动后端
python3 app_phase.py

# 2. 构建并启动前端（另一个终端）
npm run build && npm start

# 3. 运行 E2E（第三个终端）
npm run test:e2e
```

环境变量：
- `BASE_URL` — 前端地址，默认 `http://localhost:3000`
- `CHROME_PATH` — Chrome 路径，默认 macOS 系统 Chrome

E2E 测试会捕获每个页面的 JS 异常、console 错误和失败请求，任何一项
非预期错误都会导致退出码非 0。

---

## 📝 编写新测试

- 后端逻辑 → 加到 `test_adaptive_engine.py`（纯算法）或 `test_api.py`（API 行为）
- 新页面 → 把路由加进 `e2e/smoke.test.js` 顶部的 `ROUTES` 数组
- 新的页面跳转 → 加进 `HOME_NAV_TARGETS` 或 `CHAIN_PAGES`

API 测试使用 Flask test client，模板：

```python
def test_your_feature(client):
    data = client.get('/api/your-endpoint').get_json()
    assert data['success'] is True
```

注意：Flask test client 会在同一个 client 实例内保留登录 cookie。
断言"未登录应 401"的场景请使用 `anon_client` fixture。

---

## 🐛 曾由测试发现的真实 Bug（回归防线）

- `determine_review_module` 在题型统计字段为 NULL 时 TypeError（到期复习 API 500）
- 易混淆词 API 处理函数缺少 `**kwargs`，认证装饰器注入参数时 500
- 老用户带 localStorage 回访 `word-learning-entrance` 时的 React 水合错误

---

**最后更新**: 2026年7月3日

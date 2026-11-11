"""调用大模型做语义判断（第 4、6 步共用）。

DeepSeek：接口与 OpenAI 格式兼容，要求返回 JSON（response_format=json_object），思考模式用默认（开启，强度 high）。

两个接口，用环境变量 DEEPSEEK_ENDPOINT 选：
- official（默认）：官方 https://api.deepseek.com，Key 放 工具/deepseek_api_key.txt（不提交）。按量付费，
  所以出错直接报错退出，不自动重试，免得重复扣费。
- relay：免费中转站（作者 2026-11-12 拿到，2026-11-13 12:00 失效），Key 放 工具/deepseek_relay_key.txt（不提交，
  站主要求不得分发）。前面有 Cloudflare，必须带 User-Agent（urllib 默认的会被拦，403 / error code 1010）；
  开思考的长请求用流式，否则网关会 504 掐断。这台 Mac 上另有项目在用，本项目每分钟不超过 25 次请求（单 IP 合计
  超过 50 次会被封）。站主不处理故障：网关错误、断线各重试两次，还不行就停下，由作者决定是否改走官方接口
  （作者 2026-11-12：不自动切换）。

两个接口都用流式：思考可能很长，流式不会被中间的网关按超时掐断。
"""
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENDPOINTS = {
    'official': ('https://api.deepseek.com/chat/completions', HERE / 'deepseek_api_key.txt'),
    'relay': ('https://jpn.cdn.moxuna.com/v1/chat/completions', HERE / 'deepseek_relay_key.txt'),
}
ENDPOINT = os.environ.get('DEEPSEEK_ENDPOINT', 'official')
if ENDPOINT not in ENDPOINTS:
    raise SystemExit(f'DEEPSEEK_ENDPOINT 只能是 {"、".join(ENDPOINTS)}，现在是 {ENDPOINT}')
URL, KEY_FILE = ENDPOINTS[ENDPOINT]
MODELS = ('deepseek-flash', 'deepseek-v4-pro')
USER_AGENT = 'word-learning-materials/1.0'

# 中转站：每分钟最多发起这么多次请求（作者给本项目的额度是 25，留一点余量）
PER_MINUTE = int(os.environ.get('LLM_PER_MINUTE', '22'))
RELAY_RETRIES = 3


class _RateLimit:
    """滑动窗口：任意 60 秒内发起的请求不超过 PER_MINUTE 次。多个线程共用"""

    def __init__(self, per_minute):
        self.per_minute = per_minute
        self.starts = []
        self.lock = threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.time()
                self.starts = [t for t in self.starts if now - t < 60]
                if len(self.starts) < self.per_minute:
                    self.starts.append(now)
                    return
                delay = 60 - (now - self.starts[0]) + 0.05
            time.sleep(delay)


_limit = _RateLimit(PER_MINUTE)


def _key():
    key = KEY_FILE.read_text(encoding='utf-8').strip() if KEY_FILE.exists() else ''
    if not key:
        raise SystemExit(f'{KEY_FILE} 是空的：请先粘贴 DeepSeek API Key')
    return key


def _stream(body):
    """发请求，读流式回答。返回 (content, finish_reason, usage)。出错抛出原始异常，由调用方决定重试还是停下"""
    req = urllib.request.Request(URL, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _key(),
        'User-Agent': USER_AGENT, 'Accept': 'text/event-stream'})
    parts, finish, usage = [], None, {}
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode('utf-8').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            chunk = json.loads(data)
            if chunk.get('usage'):
                usage = chunk['usage']
            for choice in chunk.get('choices') or []:
                if (delta := choice.get('delta') or {}).get('content'):
                    parts.append(delta['content'])
                if choice.get('finish_reason'):
                    finish = choice['finish_reason']
    return ''.join(parts), finish, usage


def ask_json(model, system, user, max_tokens=64000):
    """发一轮对话，返回 (解析后的 JSON, 用量)。
    max_tokens 含思考：大多数词 5–12K；个别词思考超过 16K（「活动」）甚至 32K（「邮局」）、回答为空，所以留到 64K。"""
    if model not in MODELS:
        raise SystemExit(f'不认识的模型 {model}，可选：{"、".join(MODELS)}')
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'response_format': {'type': 'json_object'},
        'max_tokens': max_tokens,
        'stream': True,
        'stream_options': {'include_usage': True},
    }, ensure_ascii=False).encode()
    tries = 1 + (RELAY_RETRIES if ENDPOINT == 'relay' else 0)
    for attempt in range(1, tries + 1):
        if ENDPOINT == 'relay':
            _limit.wait()
        start = time.time()
        try:
            content, finish, usage = _stream(body)
            break
        except urllib.error.HTTPError as e:
            text = e.read()[:300].decode('utf-8', 'replace')
            detail = f'HTTP {e.code}：{text}'
            # 全站合计每分钟 1000 次的上限被别的用户占满（429，提示里是「1000次」）：和本机无关，等一分钟再发
            site_wide = e.code == 429 and '1000' in text
            # 其余 4xx（403、单 IP 的 429）可能是拦截或本机超限：再发只会更糟（封 IP），直接停
            if ENDPOINT != 'relay' or (e.code < 500 and not site_wide) or attempt == tries:
                raise SystemExit(f'DeepSeek（{ENDPOINT}）返回 {detail}')
            if site_wide:
                print(f'  中转站全站请求数满了（{detail}），65 秒后重试', flush=True)
                time.sleep(65)
                continue
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            detail = f'{type(e).__name__}: {e}'
            if attempt == tries:
                raise SystemExit(f'连接 DeepSeek（{ENDPOINT}）出错（{detail}），已停止；已完成的回答已保存，重新运行会从这里继续')
        print(f'  DeepSeek（{ENDPOINT}）出错（{detail}），{20 * attempt} 秒后重试', flush=True)
        time.sleep(20 * attempt)
    if finish != 'stop' or not content.strip():
        raise SystemExit(f'DeepSeek 回答不完整（finish_reason={finish}，长度 {len(content)}）')
    usage = dict(usage, seconds=round(time.time() - start, 1))
    try:
        return json.loads(content), usage
    except json.JSONDecodeError as e:
        raise SystemExit(f'DeepSeek 回答不是合法的 JSON（{e}）：{content[:200]!r}')

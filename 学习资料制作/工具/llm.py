"""调用大模型做语义判断（第 4、6 步共用）。

DeepSeek：接口与 OpenAI 格式兼容，要求返回 JSON（response_format=json_object），思考模式用默认（开启，强度 high）。
API Key 放在 工具/deepseek_api_key.txt（不提交）。出错直接报错退出，不自动重试，免得重复扣费。
"""
import http.client
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

KEY_FILE = Path(__file__).resolve().parent / 'deepseek_api_key.txt'
URL = 'https://api.deepseek.com/chat/completions'
MODELS = ('deepseek-flash', 'deepseek-v4-pro')


def _key():
    key = KEY_FILE.read_text(encoding='utf-8').strip() if KEY_FILE.exists() else ''
    if not key:
        raise SystemExit(f'{KEY_FILE} 是空的：请先粘贴 DeepSeek API Key')
    return key


def ask_json(model, system, user, max_tokens=32000):
    """发一轮对话，返回 (解析后的 JSON, 用量)。
    max_tokens 含思考：大多数词 5–12K，个别词（「活动」）思考超过 16K、回答为空，所以留到 32K。"""
    if model not in MODELS:
        raise SystemExit(f'不认识的模型 {model}，可选：{"、".join(MODELS)}')
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'response_format': {'type': 'json_object'},
        'max_tokens': max_tokens,
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(URL, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _key()})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'DeepSeek 返回 HTTP {e.code}：{e.read()[:300]!r}')
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
        raise SystemExit(f'连接 DeepSeek 出错（{type(e).__name__}: {e}），已停止；已完成的回答已保存，重新运行会从这里继续')
    choice = data['choices'][0]
    content = choice['message'].get('content') or ''
    if choice.get('finish_reason') != 'stop' or not content.strip():
        raise SystemExit(f'DeepSeek 回答不完整（finish_reason={choice.get("finish_reason")}，长度 {len(content)}）')
    usage = dict(data.get('usage', {}), seconds=round(time.time() - start, 1))
    return json.loads(content), usage

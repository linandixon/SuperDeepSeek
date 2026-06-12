"""复现/验证视觉副手污染主模型熔断器导致 502 的脚本。

用法:
    SUPERDS_KEY=<local_api_key> python3 scripts/repro_vision_breaker.py [base_url] [model]

    base_url 默认 http://127.0.0.1:8787
    model    默认 deepseek-v4-pro（须解析到一个不支持视觉的主模型）

旧版代码预期: 请求本身 502 "No available provider candidates"，
             且 /api/router/status 里主模型熔断器 state=open、失败数 >=3。
修复后预期:   流式请求正常返回，主模型熔断器保持 closed、失败数 0，
             vision worker 只调用配置的视觉模型，不再先打主模型。

每次运行都生成随机像素的全新 PNG，确保绕过 data/evidence.sqlite3 的内容 hash 缓存。
"""

import base64
import json
import os
import struct
import sys
import urllib.request
import zlib


def random_png() -> str:
    """生成 1x1 随机颜色 PNG 的 data URL，每次内容都不同。"""
    pixel = os.urandom(3)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00" + pixel))
    png = b"\x89PNG\r\n\x1a\n" + ihdr + idat + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def http(method: str, url: str, key: str, payload: dict = None):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    data = json.dumps(payload).encode() if payload else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=180) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def breaker_status(base: str, key: str) -> dict:
    _, body = http("GET", base + "/api/router/status", key)
    return json.loads(body).get("circuit_breakers", {})


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-pro"
    key = os.environ.get("SUPERDS_KEY", "")
    if not key:
        print("请设置 SUPERDS_KEY 环境变量（config/superds.json 里 security.local_api_key）")
        return 2

    print("== 请求前熔断器状态 ==")
    print(json.dumps(breaker_status(base, key), ensure_ascii=False, indent=1))

    content = [{"type": "text", "text": "这几张图分别是什么颜色？"}]
    content += [{"type": "image_url", "image_url": {"url": random_png()}} for _ in range(4)]
    payload = {
        "model": model,
        "stream": True,
        "max_tokens": 64,
        "messages": [{"role": "user", "content": content}],
    }
    print(f"\n== 发送 1 条流式请求（4 张全新图片，model={model}）==")
    status, body = http("POST", base + "/openai/v1/chat/completions", key, payload)
    print(f"HTTP {status}")
    print(body[:600])

    print("\n== 请求后熔断器状态 ==")
    breakers = breaker_status(base, key)
    print(json.dumps(breakers, ensure_ascii=False, indent=1))

    poisoned = [k for k, v in breakers.items() if v.get("state") != "closed" or v.get("consecutiveFailures", 0) > 0]
    if status != 200 or poisoned:
        print(f"\n[复现成功 → BUG 仍在] http={status}, 被污染的熔断器: {poisoned}")
        return 1
    print("\n[验证通过 → 修复生效] 请求成功，所有熔断器干净")
    return 0


if __name__ == "__main__":
    main_exit = main()
    sys.exit(main_exit)

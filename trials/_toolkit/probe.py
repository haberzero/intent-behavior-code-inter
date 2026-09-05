#!/usr/bin/env python3
"""
probe — LLM 端点可用性探测（试用前必做检查的自动化，规范见 LLM_SERVICE.md §三）。

读取发现的 api_config.json（复用引擎侧向上发现逻辑），对 base_url 发起
/v1/models 鉴权请求，校验配置模型在服务端可用，输出诊断与退出码。

退出码：0 = 探测通过；1 = 探测失败（配置缺失 / 服务不可达 / 鉴权失败 / 模型缺失）。

用法：
  python <toolkit>/probe.py [--start 发现起点目录，默认 CWD] [--timeout 秒]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

_TOOLKIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLKIT)
from _common import find_repo_root  # noqa: E402


def probe_connection(start_dir: str, timeout: float = 5.0) -> dict:
    """探测端点可用性，返回诊断 dict：{ok, reason, endpoint, model, latency_ms, detail}。

    配置读取复用引擎侧发现/校验逻辑（单点真理）；网络探测用标准库（不依赖 openai）。
    """
    repo_root = find_repo_root(start_dir)
    if repo_root is None:
        return {"ok": False, "reason": "repo root (main.py) not found",
                "endpoint": None, "model": None, "latency_ms": None, "detail": f"from {start_dir}"}
    sys.path.insert(0, repo_root)
    from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
    from ibci_modules.ibci_ai.config_loader import ApiConfig

    cfg_path = discover_config_path(start_dir)
    if cfg_path is None:
        return {"ok": False, "reason": "api_config.json not discovered",
                "endpoint": None, "model": None, "latency_ms": None,
                "detail": f"from {start_dir} upward (repo-bounded)"}
    try:
        raw = ApiConfig.load(cfg_path)
    except Exception as exc:  # CFG 诊断 fail-fast（含 env 引用缺失），原样作为探测诊断
        return {"ok": False, "reason": "config load failed",
                "endpoint": None, "model": None, "latency_ms": None, "detail": str(exc)}
    # ApiConfig.load 返回归一化结构：provider 连接字段已并入 default_model 条目
    dm = raw.get("default_model") or (raw.get("models") or {}).get("default") or {}
    if not (dm.get("model") and dm.get("base_url")):
        return {"ok": False, "reason": "config incomplete (default_model fields)",
                "endpoint": None, "model": None, "latency_ms": None, "detail": cfg_path}
    endpoint = dm["base_url"].rstrip("/")
    model = dm["model"]
    api_key = dm.get("api_key", "")

    url = endpoint + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        latency_ms = int((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        reason = f"auth failed (HTTP {e.code})" if e.code in (401, 403) else f"HTTP {e.code}"
        return {"ok": False, "reason": reason, "endpoint": endpoint, "model": model,
                "latency_ms": None, "detail": url}
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {"ok": False, "reason": "endpoint unreachable", "endpoint": endpoint, "model": model,
                "latency_ms": None, "detail": f"{type(e).__name__}: {e}"}
    except json.JSONDecodeError as e:
        return {"ok": False, "reason": "non-JSON response", "endpoint": endpoint, "model": model,
                "latency_ms": None, "detail": str(e)}

    ids = [m.get("id") for m in body.get("data", [])]
    if model not in ids:
        return {"ok": False, "reason": "model not served", "endpoint": endpoint, "model": model,
                "latency_ms": latency_ms, "detail": f"served: {ids}"}
    return {"ok": True, "reason": "ok", "endpoint": endpoint, "model": model,
            "latency_ms": latency_ms, "detail": "models: " + ", ".join(ids)}


def format_probe(d: dict) -> str:
    """诊断 dict → 单行摘要（batch/CLI 共用）。"""
    if d["ok"]:
        return f"OK {d['endpoint']} model={d['model']} {d['latency_ms']}ms"
    extra = " ".join(f"{k}={d[k]}" for k in ("endpoint", "model", "detail") if d.get(k) is not None)
    return f"FAIL reason={d['reason']} {extra}".rstrip()


def main():
    import argparse
    ap = argparse.ArgumentParser(description="LLM endpoint availability probe (reads discovered api_config.json).")
    ap.add_argument("--start", default=os.getcwd(), help="config discovery start dir (default CWD)")
    ap.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds")
    args = ap.parse_args()
    d = probe_connection(args.start, args.timeout)
    print("PROBE " + format_probe(d))
    sys.exit(0 if d["ok"] else 1)


if __name__ == "__main__":
    main()

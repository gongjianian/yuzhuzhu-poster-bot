from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import requests


def check_feishu() -> dict:
    try:
        start = time.time()
        from feishu_reader import build_client

        build_client()
        latency = (time.time() - start) * 1000
        return {
            "name": "Feishu API",
            "status": "ok",
            "latency_ms": round(latency, 1),
            "detail": "Connection initialized",
        }
    except Exception as exc:
        return {
            "name": "Feishu API",
            "status": "error",
            "latency_ms": None,
            "detail": str(exc),
        }


def check_gemini() -> dict:
    try:
        start = time.time()
        base_url = os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1")
        response = requests.get(
            f"{base_url}/models",
            timeout=10,
            headers={"Authorization": f"Bearer {os.getenv('GEMINI_API_KEY', '')}"},
        )
        latency = (time.time() - start) * 1000
        status = "ok" if response.status_code in (200, 401) else "error"
        return {
            "name": "Gemini API",
            "status": status,
            "latency_ms": round(latency, 1),
            "detail": f"HTTP {response.status_code}",
        }
    except Exception as exc:
        return {
            "name": "Gemini API",
            "status": "error",
            "latency_ms": None,
            "detail": str(exc),
        }


def check_wechat() -> dict:
    try:
        start = time.time()
        response = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": os.getenv("WX_APPID", ""),
                "secret": os.getenv("WX_APPSECRET", ""),
            },
            timeout=10,
        )
        latency = (time.time() - start) * 1000
        payload = response.json()
        if payload.get("access_token"):
            return {
                "name": "WeChat Cloud",
                "status": "ok",
                "latency_ms": round(latency, 1),
                "detail": "Connection ok",
            }
        return {
            "name": "WeChat Cloud",
            "status": "error",
            "latency_ms": round(latency, 1),
            "detail": payload.get("errmsg", "Unknown error"),
        }
    except Exception as exc:
        return {
            "name": "WeChat Cloud",
            "status": "error",
            "latency_ms": None,
            "detail": str(exc),
        }


def check_disk() -> dict:
    try:
        usage = shutil.disk_usage(Path.cwd())
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        status = "ok" if free_gb > 1.0 else "error"
        return {
            "name": "Disk Space",
            "status": status,
            "latency_ms": None,
            "detail": f"{free_gb:.1f}GB / {total_gb:.1f}GB available",
        }
    except Exception as exc:
        return {
            "name": "Disk Space",
            "status": "error",
            "latency_ms": None,
            "detail": str(exc),
        }


def run_all_checks() -> list[dict]:
    return [check_feishu(), check_gemini(), check_wechat(), check_disk()]

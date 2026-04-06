from __future__ import annotations

import os
import re
from datetime import datetime

from dotenv import load_dotenv
import requests


load_dotenv()


def _sanitize_path_part(value: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    return sanitized or "未分类"


def get_wx_access_token() -> str:
    response = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": os.getenv("WX_APPID", ""),
            "secret": os.getenv("WX_APPSECRET", ""),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"Failed to get WeChat access token: {payload}")
    return access_token


def upload_image(image_bytes: bytes, cloud_path: str) -> str:
    access_token = get_wx_access_token()
    response = requests.post(
        "https://api.weixin.qq.com/tcb/uploadfile",
        params={"access_token": access_token},
        json={
            "env": os.getenv("WX_ENV_ID", ""),
            "path": cloud_path,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("errcode", 0) != 0:
        raise RuntimeError(f"Failed to get upload credentials: {payload}")

    required_fields = ["url", "authorization", "token", "cos_file_id", "file_id"]
    missing_fields = [field for field in required_fields if not payload.get(field)]
    if missing_fields:
        raise RuntimeError(f"Upload credential response missing fields {missing_fields}: {payload}")

    upload_url = payload["url"]

    upload_response = requests.post(
        upload_url,
        data={
            "key": cloud_path,
            "Signature": payload["authorization"],
            "x-cos-security-token": payload["token"],
            "x-cos-meta-fileid": payload["cos_file_id"],
        },
        files={"file": ("poster.jpg", image_bytes, "image/jpeg")},
        timeout=60,
    )
    if upload_response.status_code not in (200, 201, 204):
        raise RuntimeError(f"COS upload failed: HTTP {upload_response.status_code}")

    return payload["file_id"]


def build_cloud_path(category: str, product_name: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    safe_category = _sanitize_path_part(category)
    safe_product_name = _sanitize_path_part(product_name)
    return f"images/{safe_category}/{safe_product_name}_{today}.jpg"

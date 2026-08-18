# -*- coding: utf-8 -*-
"""space ocr API のクライアント。POST /ocr/fields のみ使用。"""

import base64
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

BASE_URL = "https://api.space-ocr.com"


class SpaceOcrError(RuntimeError):
    def __init__(self, code, message, request_id=None, status=None):
        self.code = code
        self.message = message
        self.request_id = request_id
        self.status = status
        super().__init__(f"[{status} {code}] {message} (requestId={request_id})")


def _api_key() -> str:
    key = os.environ.get("SPACE_OCR_API_KEY")
    if not key:
        raise RuntimeError(
            "環境変数 SPACE_OCR_API_KEY が設定されていません。\n"
            "  export SPACE_OCR_API_KEY='spocr_...'\n"
            "APIキーはソースコードに書かないでください。"
        )
    return key


def _post(path: str, body: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(raw).get("error", {})
        except Exception:
            err = {"code": "unknown", "message": raw[:300]}
        raise SpaceOcrError(
            err.get("code", "unknown"), err.get("message", ""),
            err.get("requestId"), e.code,
        ) from None


def extract_fields(image_path: str, fields: list,
                   prompt: Optional[str] = None,
                   retries: int = 2) -> dict:
    """画像1枚から名前付きフィールドを抽出する。

    502 / 504 はエンジン側の一時的な失敗（自動返金される）ため再試行する。
    400 invalid_image は再試行しても結果が変わらないのでそのまま投げる。
    """
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    body = {"image": b64, "imageType": "base64", "fields": fields}
    if prompt:
        body["prompt"] = prompt

    last = None
    for attempt in range(retries + 1):
        try:
            res = _post("/ocr/fields", body)
            return res["data"]
        except SpaceOcrError as e:
            last = e
            if e.status in (502, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if e.status == 429 and attempt < retries:
                time.sleep(5)
                continue
            raise
    raise last


def balance() -> dict:
    req = urllib.request.Request(
        BASE_URL + "/amount",
        headers={"Authorization": f"Bearer {_api_key()}"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))

"""Loopback HTTP helpers for juno serve (ADR-06). Stdlib only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ApiResult:
    ok: bool
    status: int
    body: dict
    paused: bool = False


def _request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict | None = None,
    timeout: float = 30,
) -> ApiResult:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return ApiResult(ok=True, status=resp.status, body=body if isinstance(body, dict) else {})
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail) if detail else {}
        except json.JSONDecodeError:
            parsed = {"detail": detail}
        body = parsed if isinstance(parsed, dict) else {"detail": detail}
        return ApiResult(
            ok=False,
            status=exc.code,
            body=body,
            paused=exc.code == 423,
        )
    except URLError as exc:
        return ApiResult(ok=False, status=0, body={"detail": str(exc.reason)})


def get_status(base_url: str, token: str, *, timeout: float = 30) -> ApiResult:
    return _request("GET", base_url.rstrip("/") + "/status", token=token, timeout=timeout)


def post_ingest(base_url: str, token: str, payload: dict, *, timeout: float = 30) -> ApiResult:
    return _request(
        "POST",
        base_url.rstrip("/") + "/ingest",
        token=token,
        payload=payload,
        timeout=timeout,
    )

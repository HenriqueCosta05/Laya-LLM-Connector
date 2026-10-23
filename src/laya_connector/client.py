"""Stdlib-only HTTP client for the laya-connector daemon."""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # surfaces the 3xx as an HTTPError instead of following it


# No env proxies (a proxy would see the bearer key) and no redirects (they could carry it elsewhere).
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


class DaemonError(Exception):
    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read()[:200].decode("utf-8", "replace")
    except (OSError, http.client.HTTPException):
        return ""


def is_loopback_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class DaemonClient:
    def __init__(self, url: str, remote_key: str | None = None, timeout: float = 2.5):
        self.url = url.rstrip("/")
        self.remote_key = remote_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.remote_key and not is_loopback_url(self.url):
            headers["authorization"] = f"Bearer {self.remote_key}"
        return headers

    def _request(self, method: str, path: str, payload=None, timeout: float | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.url + path, data=data, method=method, headers=self._headers())
        try:
            with _OPENER.open(request, timeout=timeout or self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise DaemonError("auth", "remote_key invalid or missing") from exc
            raise DaemonError("http", f"{exc.code} {_read_error_body(exc)}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise DaemonError("timeout", f"no answer in {timeout or self.timeout}s") from exc
            raise DaemonError("unavailable", str(exc.reason)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise DaemonError("timeout", f"no answer in {timeout or self.timeout}s") from exc
        except http.client.HTTPException as exc:
            raise DaemonError("unavailable", f"malformed or truncated response: {exc!r}") from exc
        except OSError as exc:
            raise DaemonError("unavailable", str(exc)) from exc
        except ValueError as exc:
            raise DaemonError("http", f"invalid JSON from daemon: {exc}") from exc

    def predict(self, payload: dict, timeout: float | None = None) -> dict:
        return self._request("POST", "/v1/systemone", payload, timeout)

    def predict_batch(self, payload: dict, timeout: float | None = None) -> dict:
        return self._request("POST", "/v1/systemone/batch", payload, timeout)

    def health(self, timeout: float | None = None) -> dict:
        return self._request("GET", "/health", None, timeout)

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from frontend import mock_data


DEFAULT_API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8000")


class ApiError(RuntimeError):
    pass


@dataclass
class ApiConfig:
    mode: str = "Mock"
    base_url: str = DEFAULT_API_URL
    api_key: str = os.getenv("SENTINEL_API_KEY") or os.getenv("API_KEY", "")
    timeout: int = 90

    @property
    def live(self) -> bool:
        return self.mode == "Live"


class SentinelApi:
    def __init__(self, config: ApiConfig):
        self.config = config

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.config.api_key}

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.config.api_key:
            raise ApiError("Missing API key. Set it in the sidebar or SENTINEL_API_KEY/API_KEY.")
        timeout = kwargs.pop("timeout", self.config.timeout)
        try:
            response = requests.request(
                method,
                self._url(path),
                headers={**self._headers(), **kwargs.pop("headers", {})},
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Backend request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ApiError(f"{response.status_code} from {path}: {response.text[:300]}")
        return response.json()

    def health(self) -> dict[str, Any]:
        if not self.config.live:
            return {"status": "mock"}
        try:
            response = requests.get(self._url("/health"), timeout=5)
            return response.json()
        except requests.RequestException as exc:
            raise ApiError(f"Health check failed: {exc}") from exc

    def reports(self, **params: Any) -> dict[str, Any]:
        if not self.config.live:
            results = list(mock_data.REPORTS)
            for key in ("source_vm", "log_type", "severity"):
                value = params.get(key)
                if value and value != "All":
                    results = [item for item in results if item.get(key) == value]
            batch_id = params.get("batch_id")
            if batch_id:
                results = [item for item in results if str(item.get("batch_id")) == str(batch_id)]
            return {
                "results": results,
                "total": len(results),
                "page": params.get("page", 1),
                "page_size": params.get("page_size", 20),
            }
        clean = {k: v for k, v in params.items() if v not in (None, "", "All")}
        return self._request("GET", "/reports", params=clean)

    def batches(self, **params: Any) -> dict[str, Any]:
        if not self.config.live:
            results = list(mock_data.BATCHES)
            source_vm = params.get("source_vm")
            if source_vm and source_vm != "All":
                results = [item for item in results if item.get("source_vm") == source_vm]
            return {
                "results": results,
                "total": len(results),
                "page": params.get("page", 1),
                "page_size": params.get("page_size", 20),
            }
        clean = {k: v for k, v in params.items() if v not in (None, "", "All")}
        return self._request("GET", "/batches", params=clean)

    def integrity(self, source_vm: str | None = None) -> dict[str, Any]:
        if not self.config.live:
            if source_vm and source_vm != "All":
                item = mock_data.INTEGRITY.get(source_vm)
                return {source_vm: item} if item else {}
            return dict(mock_data.INTEGRITY)
        params = {"source_vm": source_vm} if source_vm and source_vm != "All" else None
        return self._request("GET", "/integrity", params=params)

    def query(
        self,
        question: str,
        source_vm: str | None = None,
        log_type: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if not self.config.live:
            return mock_data.mock_query(question, source_vm, log_type)
        payload = {
            "question": question,
            "source_vm": None if source_vm in (None, "All") else source_vm,
            "log_type": None if log_type in (None, "All") else log_type,
            "history": history or [],
        }
        return self._request("POST", "/query", json=payload, timeout=self.config.timeout)

    def upload(self, file_obj: Any, source_vm: str, log_type: str) -> dict[str, Any]:
        if not self.config.live:
            return {
                "filename": getattr(file_obj, "name", "uploaded.log"),
                "status": "mock-ingested",
                "batch_id": 110,
                "integrity_status": "VERIFIED",
            }
        files = {"file": (file_obj.name, file_obj.getvalue())}
        data = {"source_vm": source_vm, "log_type": log_type}
        return self._request("POST", "/upload", files=files, data=data, timeout=120)

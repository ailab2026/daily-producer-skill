#!/usr/bin/env python3
"""
Shared helpers for publish/notify URL resolution.

The daily pipeline has three distinct concepts:
1. Generated artifacts in output/daily
2. Preview URLs served by feedback_server.py
3. Published artifacts copied to a public directory/path

Keeping these rules in one place avoids broken links when the skill is shared.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT_DIR / "config" / "profile.yaml"
OUTPUT_DIR = ROOT_DIR / "output"
DAILY_OUTPUT_DIR = OUTPUT_DIR / "daily"


def load_profile(profile_path: Path | None = None) -> dict[str, Any]:
    profile_path = profile_path or PROFILE_PATH
    if not profile_path.exists():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_nested(data: dict[str, Any], key_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in key_path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
    return current


def _normalize_url_path(raw: str, default: str = "/daily") -> str:
    value = (raw or "").strip()
    if not value:
        value = default
    if not value.startswith("/"):
        value = "/" + value
    value = value.rstrip("/")
    return value or default


def _resolve_path(raw: str, *, root: Path = ROOT_DIR, default: str = "") -> Path | None:
    value = (raw or default).strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def _target_dir_candidates() -> list[tuple[str, Path]]:
    candidates = [
        OUTPUT_DIR / "rwa" / "daily",
        OUTPUT_DIR / "public" / "daily",
        OUTPUT_DIR / "site" / "daily",
        OUTPUT_DIR / "www" / "daily",
    ]
    found: list[tuple[str, Path]] = []
    for path in candidates:
        if path.exists() and path.is_dir():
            try:
                rel = path.relative_to(ROOT_DIR)
                found.append((str(rel), path))
            except ValueError:
                found.append((str(path), path))
    if not found and DAILY_OUTPUT_DIR.exists() and DAILY_OUTPUT_DIR.is_dir():
        found.append(("output/daily", DAILY_OUTPUT_DIR))
    return found


def _infer_target_dir() -> tuple[str, Path | None, list[tuple[str, Path]]]:
    """
    Infer a publish target directory from the current workspace.

    Preference order:
    1. Existing common public dirs under output/
    2. Existing output/daily as last-resort same-dir publish mode
    """
    candidates = _target_dir_candidates()
    if candidates:
        raw, path = candidates[0]
        return raw, path, candidates
    return "", None, []


def _infer_public_daily_path(target_dir: Path | None) -> str:
    if isinstance(target_dir, Path):
        try:
            rel = target_dir.relative_to(OUTPUT_DIR)
            return _normalize_url_path("/" + rel.as_posix(), default="/daily")
        except ValueError:
            pass
    return "/daily"


def get_publish_config(
    profile: dict[str, Any] | None = None,
    *,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    profile = profile or load_profile(profile_path)
    publish_cfg = get_nested(profile, "publish", {}) or {}
    server_cfg = get_nested(profile, "server", {}) or {}

    explicit_target_dir_raw = str(publish_cfg.get("target_dir", "") or "").strip()
    inferred_target_dir_raw, inferred_target_dir, target_candidates = _infer_target_dir()
    target_dir_raw = explicit_target_dir_raw or inferred_target_dir_raw
    resolved_target_dir = _resolve_path(target_dir_raw)
    if resolved_target_dir is None and inferred_target_dir is not None:
        resolved_target_dir = inferred_target_dir

    explicit_public_base_url = str(publish_cfg.get("public_base_url", "") or "").rstrip("/")
    preview_base_url = str(server_cfg.get("public_url", "") or "").rstrip("/")
    public_base_url = explicit_public_base_url or preview_base_url

    explicit_public_daily_path = str(publish_cfg.get("public_daily_path", "") or "").strip()
    inferred_public_daily_path = _infer_public_daily_path(resolved_target_dir)
    public_daily_path = _normalize_url_path(
        explicit_public_daily_path or inferred_public_daily_path,
        default="/daily",
    )
    status_dir_raw = str(publish_cfg.get("status_dir", "") or "output/publish")

    enabled_raw = publish_cfg.get("enabled")
    if isinstance(enabled_raw, bool):
        enabled = enabled_raw
    else:
        enabled = bool(target_dir_raw or public_base_url)

    return {
        "enabled": enabled,
        "target_dir_raw": target_dir_raw,
        "target_dir": resolved_target_dir,
        "status_dir_raw": status_dir_raw,
        "status_dir": _resolve_path(status_dir_raw, default="output/publish"),
        "public_base_url": public_base_url,
        "public_daily_path": public_daily_path,
        "inferred_public_daily_path": inferred_public_daily_path,
        "preview_base_url": preview_base_url,
        "target_dir_candidates": [
            {"raw": raw, "path": str(path.resolve())} for raw, path in target_candidates
        ],
        "auto_detected": {
            "target_dir": not bool(explicit_target_dir_raw) and bool(target_dir_raw),
            "public_base_url": not bool(explicit_public_base_url) and bool(public_base_url),
            "public_daily_path": not bool(explicit_public_daily_path) and bool(public_daily_path),
        },
        "needs_confirmation": {
            "target_dir": not bool(explicit_target_dir_raw) and len(target_candidates) > 1,
        },
    }


def source_report_path(date_str: str, ext: str, *, root: Path = ROOT_DIR) -> Path:
    return root / "output" / "daily" / f"{date_str}.{ext.lstrip('.')}"


def target_report_path(date_str: str, ext: str, publish_cfg: dict[str, Any]) -> Path | None:
    target_dir = publish_cfg.get("target_dir")
    if not isinstance(target_dir, Path):
        return None
    return target_dir / f"{date_str}.{ext.lstrip('.')}"


def build_report_url(base_url: str, daily_path: str, date_str: str, ext: str = "html") -> str:
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        return ""
    daily_path = _normalize_url_path(daily_path)
    return f"{base_url}{daily_path}/{date_str}.{ext.lstrip('.')}"


def build_public_report_url(date_str: str, publish_cfg: dict[str, Any], ext: str = "html") -> str:
    return build_report_url(
        publish_cfg.get("public_base_url", ""),
        publish_cfg.get("public_daily_path", "/daily"),
        date_str,
        ext=ext,
    )


def build_preview_report_url(date_str: str, publish_cfg: dict[str, Any], ext: str = "html") -> str:
    return build_report_url(
        publish_cfg.get("preview_base_url", ""),
        "/daily",
        date_str,
        ext=ext,
    )


def publish_status_path(date_str: str, publish_cfg: dict[str, Any]) -> Path:
    status_dir = publish_cfg.get("status_dir")
    if not isinstance(status_dir, Path):
        raise ValueError("publish.status_dir 未配置")
    return status_dir / f"{date_str}.json"


def load_publish_status(date_str: str, publish_cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    publish_cfg = publish_cfg or get_publish_config()
    try:
        path = publish_status_path(date_str, publish_cfg)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_publish_status(date_str: str, payload: dict[str, Any], publish_cfg: dict[str, Any] | None = None) -> Path:
    publish_cfg = publish_cfg or get_publish_config()
    path = publish_status_path(date_str, publish_cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data.setdefault("date", date_str)
    data.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def resolve_notification_report_url(date_str: str) -> str:
    """
    Resolve the HTML URL that notifications should use.

    Rules:
    - If publish is configured, only return a URL when the published artifact exists.
      This prevents silently sending preview URLs when publishing failed.
    - If publish is not configured, fall back to feedback_server's preview URL.
    """
    publish_cfg = get_publish_config()
    publish_expected = bool(
        publish_cfg.get("enabled")
        or publish_cfg.get("target_dir_raw")
        or publish_cfg.get("public_base_url")
    )

    if publish_expected:
        status = load_publish_status(date_str, publish_cfg)
        if status:
            artifacts = status.get("artifacts", {}) if isinstance(status.get("artifacts"), dict) else {}
            html_meta = artifacts.get("html", {}) if isinstance(artifacts.get("html"), dict) else {}
            target_path = str(html_meta.get("target_path", "") or "")
            public_url = str(html_meta.get("url", "") or status.get("public_url", "") or "")
            if target_path and Path(target_path).exists() and public_url:
                return public_url

        target_html = target_report_path(date_str, "html", publish_cfg)
        public_url = build_public_report_url(date_str, publish_cfg, ext="html")
        if target_html and target_html.exists() and public_url:
            return public_url
        return ""

    source_html = source_report_path(date_str, "html")
    preview_url = build_preview_report_url(date_str, publish_cfg, ext="html")
    if source_html.exists() and preview_url:
        return preview_url
    return ""

#!/usr/bin/env python3
"""
Detect publish configuration from the current environment.

Usage:
    python3 scripts/detect_publish_config.py
    python3 scripts/detect_publish_config.py --json
    python3 scripts/detect_publish_config.py --yaml-snippet
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from publish_utils import get_publish_config


def _payload() -> dict[str, Any]:
    cfg = get_publish_config()
    target_dir = cfg.get("target_dir")
    return {
        "publish": {
            "enabled": bool(cfg.get("enabled")),
            "target_dir": cfg.get("target_dir_raw", ""),
            "public_base_url": cfg.get("public_base_url", ""),
            "public_daily_path": cfg.get("public_daily_path", ""),
            "status_dir": cfg.get("status_dir_raw", "output/publish"),
        },
        "resolved": {
            "target_dir": str(target_dir) if target_dir else "",
            "preview_base_url": cfg.get("preview_base_url", ""),
        },
        "auto_detected": cfg.get("auto_detected", {}),
        "needs_confirmation": cfg.get("needs_confirmation", {}),
        "target_dir_candidates": cfg.get("target_dir_candidates", []),
    }


def _yaml_snippet(data: dict[str, Any]) -> str:
    publish = data["publish"]
    lines = [
        "publish:",
        f"  enabled: {'true' if publish['enabled'] else 'false'}",
        f"  target_dir: \"{publish['target_dir']}\"",
        f"  public_base_url: \"{publish['public_base_url']}\"",
        f"  public_daily_path: \"{publish['public_daily_path']}\"",
        f"  status_dir: \"{publish['status_dir']}\"",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="自动探测日报发布配置")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--yaml-snippet", action="store_true", help="输出可写入 profile.yaml 的 YAML 片段")
    args = parser.parse_args()

    data = _payload()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if args.yaml_snippet:
        print(_yaml_snippet(data))
        return

    publish = data["publish"]
    resolved = data["resolved"]
    print("Publish config detection")
    print(f"  target_dir: {publish['target_dir'] or '(未探测到)'}")
    print(f"  public_base_url: {publish['public_base_url'] or '(未探测到)'}")
    print(f"  public_daily_path: {publish['public_daily_path'] or '(未探测到)'}")
    print(f"  status_dir: {publish['status_dir']}")
    auto = [k for k, v in data.get("auto_detected", {}).items() if v]
    if auto:
        print(f"  auto_detected: {', '.join(auto)}")
    if resolved.get("preview_base_url"):
        print(f"  preview_base_url: {resolved['preview_base_url']}")
    candidates = data.get("target_dir_candidates", [])
    if candidates:
        print("  target_dir_candidates:")
        for item in candidates:
            print(f"    - {item['raw']} -> {item['path']}")
    confirm = data.get("needs_confirmation", {})
    if isinstance(confirm, dict) and any(confirm.values()):
        print("  needs_confirmation: yes")
    else:
        print("  needs_confirmation: no")


if __name__ == "__main__":
    main()

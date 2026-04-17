#!/usr/bin/env python3
"""
Write auto-detected publish settings back to config/profile.yaml.

Default behavior is conservative:
- only fill missing publish fields
- do not overwrite explicit values unless --force is used
- stop when target_dir detection is ambiguous
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from publish_utils import PROFILE_PATH, get_nested, get_publish_config, load_profile


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_str(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def _render_publish_block(publish: dict[str, Any]) -> str:
    return "\n".join(
        [
            "publish:",
            f"  enabled: {_yaml_bool(bool(publish.get('enabled')))}",
            f"  target_dir: {_yaml_str(str(publish.get('target_dir', '') or ''))}  # 发布目录；留空时会尝试自动识别常见目录",
            f"  public_base_url: {_yaml_str(str(publish.get('public_base_url', '') or ''))}  # 公开站点域名；留空时会回退到 server.public_url",
            f"  public_daily_path: {_yaml_str(str(publish.get('public_daily_path', '') or ''))}  # 公开日报 URL 前缀；留空时会根据 target_dir 自动推断",
            f"  status_dir: {_yaml_str(str(publish.get('status_dir', '') or 'output/publish'))}",
        ]
    )


def _replace_top_level_block(text: str, block_name: str, new_block: str) -> str:
    lines = text.splitlines(keepends=True)
    key_re = re.compile(rf"^{re.escape(block_name)}:\s*(?:#.*)?$")
    top_level_re = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*:\s*(?:#.*)?$")

    start = next((i for i, line in enumerate(lines) if key_re.match(line.rstrip("\n"))), None)
    if start is not None:
        end = start + 1
        while end < len(lines):
            stripped = lines[end].rstrip("\n")
            if stripped and not lines[end].startswith((" ", "\t")) and top_level_re.match(stripped):
                break
            end += 1
        replacement = new_block.rstrip() + "\n\n"
        return "".join(lines[:start] + [replacement] + lines[end:])

    anchor = next((i for i, line in enumerate(lines) if re.match(r"^server:\s*(?:#.*)?$", line.rstrip("\n"))), None)
    if anchor is not None:
        end = anchor + 1
        while end < len(lines):
            stripped = lines[end].rstrip("\n")
            if stripped and not lines[end].startswith((" ", "\t")) and top_level_re.match(stripped):
                break
            end += 1
        insertion = "\n" + new_block.rstrip() + "\n"
        return "".join(lines[:end] + [insertion] + lines[end:])

    suffix = "" if text.endswith("\n") else "\n"
    return text + suffix + "\n" + new_block.rstrip() + "\n"


def _resolve_final_publish_values(profile: dict[str, Any], detected: dict[str, Any], force: bool) -> dict[str, Any]:
    current = get_nested(profile, "publish", {}) or {}

    current_target_dir = str(current.get("target_dir", "") or "").strip()
    current_public_base_url = str(current.get("public_base_url", "") or "").strip()
    current_public_daily_path = str(current.get("public_daily_path", "") or "").strip()
    current_status_dir = str(current.get("status_dir", "") or "").strip()

    detected_target_dir = str(detected.get("target_dir_raw", "") or "").strip()
    detected_public_base_url = str(detected.get("public_base_url", "") or "").strip()
    detected_public_daily_path = str(detected.get("public_daily_path", "") or "").strip()
    inferred_public_daily_path = str(detected.get("inferred_public_daily_path", "") or "").strip()
    detected_status_dir = str(detected.get("status_dir_raw", "output/publish") or "output/publish").strip()

    final_target_dir = detected.get("target_dir_raw", "") if force or not current_target_dir else current_target_dir
    final_public_base_url = (
        detected_public_base_url
        if force or not current_public_base_url
        else current_public_base_url
    )
    current_path_is_default = current_public_daily_path in ("", "/daily")
    detected_path_is_specific = bool(inferred_public_daily_path and inferred_public_daily_path != "/daily")
    if force or not current_public_daily_path:
        final_public_daily_path = detected_public_daily_path
    elif not current_target_dir and current_path_is_default and detected_path_is_specific:
        # Treat template "/daily" as replaceable when a more specific path is inferred.
        final_public_daily_path = inferred_public_daily_path
    else:
        final_public_daily_path = current_public_daily_path
    final_status_dir = (
        detected_status_dir
        if force or not current_status_dir
        else current_status_dir
    )

    current_enabled = current.get("enabled")
    meaningful_explicit_publish_values = any(
        [
            current_target_dir,
            current_public_base_url,
            current_public_daily_path not in ("", "/daily"),
            current_status_dir not in ("", "output/publish"),
        ]
    )
    detected_enabled = bool(
        final_target_dir or final_public_base_url or detected_target_dir or detected_public_base_url
    )
    if force:
        final_enabled = detected_enabled
    elif "enabled" not in current:
        final_enabled = detected_enabled
    elif current_enabled is False and not meaningful_explicit_publish_values and detected_enabled:
        # Template default "enabled: false" should not block first-time auto setup.
        final_enabled = True
    else:
        final_enabled = bool(current_enabled)

    return {
        "enabled": final_enabled,
        "target_dir": final_target_dir,
        "public_base_url": final_public_base_url,
        "public_daily_path": final_public_daily_path,
        "status_dir": final_status_dir or "output/publish",
    }


def _changed_fields(profile: dict[str, Any], final_publish: dict[str, Any]) -> list[str]:
    current = get_nested(profile, "publish", {}) or {}
    fields = []
    for key, new_value in final_publish.items():
        old_value = current.get(key)
        if key == "enabled":
            if bool(old_value) != bool(new_value):
                fields.append(key)
            continue
        if str(old_value or "") != str(new_value or ""):
            fields.append(key)
    return fields


def _emit(status: str, payload: dict[str, Any], *, as_json: bool) -> None:
    data = {"status": status, **payload}
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if status == "applied":
        print(f"已更新 {payload['profile_path']}")
        changed = payload.get("changed_fields", [])
        print(f"changed_fields: {', '.join(changed)}")
        return
    if status == "no_change":
        print(f"publish 配置无需更新: {payload['profile_path']}")
        return
    if status == "needs_confirmation":
        print("ERROR: 检测到多个 publish.target_dir 候选目录，需先让用户确认。", file=sys.stderr)
        return
    print(str(payload.get("error", "未知错误")), file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="自动探测并回写 publish 配置")
    parser.add_argument(
        "--profile",
        default=str(PROFILE_PATH),
        help="要写入的 profile.yaml 路径，默认使用 config/profile.yaml",
    )
    parser.add_argument("--force", action="store_true", help="覆盖当前已填写的 publish 配置")
    parser.add_argument("--dry-run", action="store_true", help="仅显示将要写入的内容，不落盘")
    parser.add_argument("--json", action="store_true", help="输出结构化结果，便于 agent 在初始化流程里判断")
    args = parser.parse_args()

    profile_path = Path(args.profile).expanduser()
    profile = load_profile(profile_path)
    if not profile_path.exists():
        _emit(
            "error",
            {
                "profile_path": str(profile_path),
                "error": f"profile 不存在: {profile_path}",
            },
            as_json=args.json,
        )
        sys.exit(1)
    if not isinstance(profile, dict) or not profile:
        _emit(
            "error",
            {
                "profile_path": str(profile_path),
                "error": f"profile 解析失败或为空: {profile_path}",
            },
            as_json=args.json,
        )
        sys.exit(1)

    detected = get_publish_config(profile, profile_path=profile_path)
    needs_confirmation = detected.get("needs_confirmation", {}) or {}
    current_publish = get_nested(profile, "publish", {}) or {}
    current_target_dir = str(current_publish.get("target_dir", "") or "").strip()
    payload_base = {
        "profile_path": str(profile_path),
        "publish": {
            "enabled": bool(detected.get("enabled")),
            "target_dir": str(detected.get("target_dir_raw", "") or ""),
            "public_base_url": str(detected.get("public_base_url", "") or ""),
            "public_daily_path": str(detected.get("public_daily_path", "") or ""),
            "status_dir": str(detected.get("status_dir_raw", "output/publish") or "output/publish"),
        },
        "needs_confirmation": needs_confirmation,
        "target_dir_candidates": detected.get("target_dir_candidates", []),
    }

    if needs_confirmation.get("target_dir") and not current_target_dir and not args.force:
        _emit("needs_confirmation", payload_base, as_json=args.json)
        sys.exit(2)

    final_publish = _resolve_final_publish_values(profile, detected, force=args.force)
    changed = _changed_fields(profile, final_publish)
    block = _render_publish_block(final_publish)
    payload = {
        **payload_base,
        "publish": final_publish,
        "changed_fields": changed,
    }

    if args.dry_run:
        if args.json:
            payload["yaml_snippet"] = block
            _emit("dry_run", payload, as_json=True)
            return
        print(block)
        print(f"\n# changed_fields: {', '.join(changed) if changed else '(none)'}")
        return

    if not changed:
        _emit("no_change", payload, as_json=args.json)
        return

    original_text = profile_path.read_text(encoding="utf-8")
    updated_text = _replace_top_level_block(original_text, "publish", block)
    profile_path.write_text(updated_text, encoding="utf-8")

    _emit("applied", payload, as_json=args.json)


if __name__ == "__main__":
    main()

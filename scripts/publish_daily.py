#!/usr/bin/env python3
"""
Publish generated daily artifacts to a public directory and write publish status.

Usage:
    python3 scripts/publish_daily.py --date 2026-04-17
    python3 scripts/publish_daily.py --date 2026-04-17 --print-url
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from publish_utils import (
    ROOT_DIR,
    build_public_report_url,
    get_publish_config,
    source_report_path,
    target_report_path,
    write_publish_status,
)


def _copy_or_skip(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="发布今日日报到公开目录")
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="目标日期，格式 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅输出计划，不实际复制")
    parser.add_argument("--print-url", action="store_true", help="成功后仅输出公开 HTML URL")
    args = parser.parse_args()

    publish_cfg = get_publish_config()
    target_dir = publish_cfg.get("target_dir")
    if not isinstance(target_dir, Path):
        print(
            "ERROR: 无法确定 publish.target_dir。请在 config/profile.yaml 中设置发布目录，或先创建常见公开目录（如 output/rwa/daily）。",
            file=sys.stderr,
        )
        sys.exit(1)

    source_html = source_report_path(args.date, "html")
    source_json = source_report_path(args.date, "json")
    missing = [str(p) for p in (source_html, source_json) if not p.exists()]
    if missing:
        print("ERROR: 以下源文件不存在，请先完成生成/渲染：", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        sys.exit(1)

    target_html = target_report_path(args.date, "html", publish_cfg)
    target_json = target_report_path(args.date, "json", publish_cfg)
    assert target_html is not None and target_json is not None

    html_url = build_public_report_url(args.date, publish_cfg, ext="html")
    json_url = build_public_report_url(args.date, publish_cfg, ext="json")

    if args.dry_run:
        print(f"source html: {source_html}")
        print(f"source json: {source_json}")
        print(f"target html: {target_html}")
        print(f"target json: {target_json}")
        print(f"public html: {html_url or '(未配置)'}")
        print(f"public json: {json_url or '(未配置)'}")
        return

    _copy_or_skip(source_html, target_html)
    _copy_or_skip(source_json, target_json)

    if not target_html.exists() or not target_json.exists():
        print("ERROR: 发布后目标文件缺失，请检查目标目录权限。", file=sys.stderr)
        sys.exit(1)

    status_path = write_publish_status(
        args.date,
        {
            "success": True,
            "mode": "filesystem_copy",
            "source_dir": str((ROOT_DIR / "output" / "daily").resolve()),
            "target_dir": str(target_dir.resolve()),
            "public_url": html_url,
            "artifacts": {
                "html": {
                    "source_path": str(source_html.resolve()),
                    "target_path": str(target_html.resolve()),
                    "url": html_url,
                    "size": target_html.stat().st_size,
                },
                "json": {
                    "source_path": str(source_json.resolve()),
                    "target_path": str(target_json.resolve()),
                    "url": json_url,
                    "size": target_json.stat().st_size,
                },
            },
        },
        publish_cfg,
    )

    if args.print_url:
        if not html_url:
            print("ERROR: publish.public_base_url 未配置，无法输出公开 URL。", file=sys.stderr)
            sys.exit(1)
        print(html_url)
        return

    print("✅ 日报已发布")
    print(f"   日期: {args.date}")
    print(f"   HTML: {target_html}")
    print(f"   JSON: {target_json}")
    print(f"   公开 HTML: {html_url or '(未配置 publish.public_base_url)'}")
    print(f"   状态文件: {status_path}")
    auto = publish_cfg.get("auto_detected", {})
    if isinstance(auto, dict):
        inferred = [name for name, flag in auto.items() if flag]
        if inferred:
            print(f"   自动推断: {', '.join(inferred)}")


if __name__ == "__main__":
    main()

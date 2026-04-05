#!/usr/bin/env python3
"""
校验日报 JSON 是否符合渲染器契约。
大模型生成 JSON 后必须跑一遍，不通过就报错让它改。

用法：
    python3 scripts/validate_payload.py output/daily/2026-04-05.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def validate(data: dict) -> list[str]:
    """校验日报 JSON，返回错误列表。空列表 = 通过。"""
    errors = []

    # ━━ meta ━━
    meta = data.get("meta")
    if not meta:
        errors.append("[meta] 缺失")
    else:
        for field in ("date", "date_label", "role"):
            if not meta.get(field):
                errors.append(f"[meta.{field}] 缺失或为空")
        # date 格式
        date = meta.get("date", "")
        if date and len(date) != 10:
            errors.append(f"[meta.date] 格式应为 YYYY-MM-DD，当前: {date}")

    # ━━ left_sidebar ━━
    sidebar = data.get("left_sidebar")
    if not sidebar:
        errors.append("[left_sidebar] 缺失")
    else:
        # overview
        overview = sidebar.get("overview")
        if not overview or not isinstance(overview, list):
            errors.append("[left_sidebar.overview] 缺失或不是数组")
        elif len(overview) < 2:
            errors.append(f"[left_sidebar.overview] 至少 2 条，当前 {len(overview)} 条")
        else:
            for i, item in enumerate(overview):
                if not item.get("title"):
                    errors.append(f"[left_sidebar.overview[{i}].title] 缺失")
                if not item.get("text"):
                    errors.append(f"[left_sidebar.overview[{i}].text] 缺失")

        # actions
        actions = sidebar.get("actions")
        if not actions or not isinstance(actions, list):
            errors.append("[left_sidebar.actions] 缺失或不是数组")
        elif len(actions) < 2:
            errors.append(f"[left_sidebar.actions] 至少 2 条，当前 {len(actions)} 条")
        else:
            valid_types = {"learn", "try", "watch", "alert"}
            for i, item in enumerate(actions):
                if not item.get("text"):
                    errors.append(f"[left_sidebar.actions[{i}].text] 缺失")
                if not item.get("prompt"):
                    errors.append(f"[left_sidebar.actions[{i}].prompt] 缺失")
                if item.get("type") and item["type"] not in valid_types:
                    errors.append(f"[left_sidebar.actions[{i}].type] 无效: {item['type']}，应为 {valid_types}")

        # trends
        trends = sidebar.get("trends")
        if not trends:
            errors.append("[left_sidebar.trends] 缺失")
        else:
            for field in ("rising", "cooling", "steady"):
                if not trends.get(field) or not isinstance(trends[field], list):
                    errors.append(f"[left_sidebar.trends.{field}] 缺失或不是数组")
            if not trends.get("insight"):
                errors.append("[left_sidebar.trends.insight] 缺失")

    # ━━ articles ━━
    articles = data.get("articles")
    if not articles or not isinstance(articles, list):
        errors.append("[articles] 缺失或不是数组")
    elif len(articles) < 5:
        errors.append(f"[articles] 至少 5 条，当前 {len(articles)} 条")
    else:
        valid_priorities = {"major", "notable", "normal", "minor"}
        seen_ids = set()
        for i, article in enumerate(articles):
            prefix = f"[articles[{i}]]"

            # 必需字段
            for field in ("id", "title", "priority", "source", "url"):
                if not article.get(field):
                    errors.append(f"{prefix}.{field} 缺失或为空")

            # id 唯一性
            aid = article.get("id", "")
            if aid in seen_ids:
                errors.append(f"{prefix}.id 重复: {aid}")
            seen_ids.add(aid)

            # priority 值
            priority = article.get("priority", "")
            if priority and priority not in valid_priorities:
                errors.append(f"{prefix}.priority 无效: {priority}，应为 {valid_priorities}")

            # summary
            summary = article.get("summary")
            if not summary or not isinstance(summary, dict):
                errors.append(f"{prefix}.summary 缺失或不是对象")
            else:
                if not summary.get("what_happened"):
                    errors.append(f"{prefix}.summary.what_happened 缺失")
                if not summary.get("why_it_matters"):
                    errors.append(f"{prefix}.summary.why_it_matters 缺失")

            # relevance
            if not article.get("relevance"):
                errors.append(f"{prefix}.relevance 缺失")

            # tags
            tags = article.get("tags")
            if not tags or not isinstance(tags, list):
                errors.append(f"{prefix}.tags 缺失或不是数组")

            # url 格式
            url = article.get("url", "")
            if url and not url.startswith("http"):
                errors.append(f"{prefix}.url 格式错误: {url[:50]}")

            # credibility（可选但推荐）
            cred = article.get("credibility")
            if cred:
                if cred.get("confidence") and cred["confidence"] not in ("high", "medium", "low"):
                    errors.append(f"{prefix}.credibility.confidence 无效: {cred['confidence']}")

    # ━━ data_sources ━━
    if not data.get("data_sources") or not isinstance(data.get("data_sources"), list):
        errors.append("[data_sources] 缺失或不是数组")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/validate_payload.py <json_file>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: {path} 不存在", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate(data)

    if not errors:
        articles = data.get("articles", [])
        print(f"✅ 校验通过")
        print(f"   日期: {data.get('meta', {}).get('date', '?')}")
        print(f"   文章: {len(articles)} 条")
        priorities = {}
        for a in articles:
            p = a.get("priority", "unknown")
            priorities[p] = priorities.get(p, 0) + 1
        print(f"   优先级: {priorities}")
        print(f"   速览: {len(data.get('left_sidebar', {}).get('overview', []))} 条")
        print(f"   行动: {len(data.get('left_sidebar', {}).get('actions', []))} 条")
    else:
        print(f"❌ 校验失败，{len(errors)} 个错误：")
        for e in errors:
            print(f"   {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

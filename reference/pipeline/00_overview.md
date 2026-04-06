# 日报生产流水线总览

## 流程

```
01 build_queries.py              生成搜索查询（关键词 cn/en 分组）
        ↓
02 collect_sources_with_opencli.py  采集候选池（21 个平台/网站）
        ↓
03 filter_index.py               时间筛选（保留 3 天内 + 网站类）
        ↓
04 collect_detail.py             深抓正文（网站类用 web read）
        ↓
05 prepare_payload.py            去噪打分（profile 关键词匹配）
        ↓
06 【AI 执行】                    生成日报 JSON（选 15 条 + 写 summary + sidebar）
        ↓
07 validate_payload.py           校验 JSON（不通过则回到 06 修改）
        ↓
08 render_daily.py               渲染 HTML
```

## 一键执行

```bash
cd /root/.openclaw/workspaces/dailynew/skills/daily-producer-skill

DATE=2026-04-06

# 步骤 01-05（脚本自动化）
python3 scripts/build_queries.py --date $DATE --window 3
python3 scripts/collect_sources_with_opencli.py --date $DATE --max-keywords 5 --max-results 5
python3 scripts/filter_index.py --date $DATE --window 3
python3 scripts/collect_detail.py --date $DATE
python3 scripts/prepare_payload.py --date $DATE

# 步骤 06（AI 读取 candidates.json 生成日报 JSON）
# → output/daily/$DATE.json

# 步骤 07-08（脚本验证+渲染）
python3 scripts/validate_payload.py output/daily/$DATE.json
python3 scripts/render_daily.py output/daily/$DATE.json --force
```

## 产出文件

| 步骤 | 文件 | 说明 |
|------|------|------|
| 01 | `output/raw/{date}_queries.txt` | 搜索查询列表 |
| 02 | `output/raw/{date}_index.txt` | 原始候选池 |
| 03 | `output/raw/{date}_index_filtered.txt` | 时间筛选后 |
| 04 | `output/raw/{date}_detail.txt` | 深抓详情 |
| 05 | `output/raw/{date}_candidates.json` | 去噪打分后的结构化候选 |
| 06 | `output/daily/{date}.json` | 最终日报 JSON |
| 07 | （无文件，校验结果输出到 stdout） | — |
| 08 | `output/daily/{date}.html` | 日报 HTML 页面 |

## 数据量变化（典型）

```
01  90 条查询
02  ~950 条原始候选
03  ~130 条（时间筛选后）
04  ~90 条（平台类直接保留 + 网站类深抓）
05  ~70 条（去噪后）
06  15 条（AI 精选）
```

## 各步骤详细文档

- [01_build_queries.md](01_build_queries.md)
- [02_collect_sources.md](02_collect_sources.md)
- [03_filter_index.md](03_filter_index.md)
- [04_collect_detail.md](04_collect_detail.md)
- [05_prepare_payload.md](05_prepare_payload.md)
- [06_generate_json.md](06_generate_json.md)
- [07_validate_payload.md](07_validate_payload.md)
- [08_render_html.md](08_render_html.md)

---
name: daily-producer
description: 每日一报生产引擎。从用户画像出发，自动采集多平台资讯，筛选去噪，AI 生成结构化日报，渲染为 HTML。
---

# Daily Producer Skill

个性化每日资讯日报的完整生产系统。

## 启动协议

当用户表达"生成日报 / 跑 daily / 今天的日报"时：

1. **读取 `config/profile.yaml`**
2. **不存在** → 读取并执行 `init/daily-init.md` 初始化流程（参考 `reference/profile_template.yaml` 模板）
3. **存在** → 进入日报生产流程

**禁止：** 未读取 profile 就问用户"你关注什么"；profile 存在时主动触发初始化。

---

## 生产流水线

共 8 步。步骤 01-05 有自动化脚本，步骤 06 由 AI 执行，步骤 07-08 由脚本完成。

**每步的详细说明、参数、输入输出格式见 `reference/pipeline/` 目录。**

```
profile.yaml
    ↓
01  build_queries.py           生成搜索查询
    ↓
02  collect_sources_with_opencli.py  采集候选池
    ↓
03  filter_index.py            时间筛选
    ↓
04  collect_detail.py          深抓正文
    ↓
05  prepare_payload.py         去噪打分
    ↓
06  【AI】                     生成日报 JSON
    ↓
07  validate_payload.py        校验 JSON
    ↓
08  render_daily.py            渲染 HTML
```

### Step 01: 生成搜索查询

从 profile 的 topics/keywords 生成两类查询：platform（纯关键词给各平台搜索）和 google（带 `after:` 日期过滤）。

```bash
python3 scripts/build_queries.py --date {date} --window 3
```

→ 详见 `reference/pipeline/01_build_queries.md`

### Step 02: 采集候选池

用 opencli 从 profile 配置的所有平台（微博/小红书/B站/Twitter/Reddit 等）和网站（机器之心/量子位/TechCrunch 等）采集资讯。

```bash
python3 scripts/collect_sources_with_opencli.py --date {date} --max-keywords 5 --max-results 5
```

- 采集前自动运行 `opencli doctor` 检查连接
- cn 关键词分发给国内平台，en 关键词分发给国外平台
- Reddit 自动探测 opencli 可用性，不通走 API+代理
- 每次请求间隔 3 秒防限流

→ 详见 `reference/pipeline/02_collect_sources.md`
→ 各平台输出字段参考 `reference/opencli_output_formats.md`

### Step 03: 时间筛选

过滤掉超出时间窗口的旧内容。无时间字段的条目直接过滤，网站类条目（Google site: 搜索自带时间过滤）直接保留。

```bash
python3 scripts/filter_index.py --date {date} --window 3
```

→ 详见 `reference/pipeline/03_filter_index.md`

### Step 04: 深抓正文

平台类条目已有完整内容（直接保留），网站类条目只有标题+URL（用 `opencli web read` 抓正文）。同一 URL 不重复抓取。

```bash
python3 scripts/collect_detail.py --date {date}
```

→ 详见 `reference/pipeline/04_collect_detail.md`

### Step 05: 去噪打分

基于 profile 关键词匹配度过滤噪音（不用硬编码黑名单，通用于任何画像），按热度+关键词匹配打分排序。

```bash
python3 scripts/prepare_payload.py --date {date}
```

→ 详见 `reference/pipeline/05_prepare_payload.md`

### Step 06: AI 生成日报 JSON（核心）

AI 读取 `output/raw/{date}_candidates.json`，从候选中选出 15 条，写 summary/relevance/sidebar，生成日报 JSON。

**必须参考：**
- `reference/pipeline/06_generate_json.md` — 生成规则和 JSON 结构
- `reference/daily_payload_example.json` — 结构示例
- `config/profile.yaml` — 用户画像（决定 relevance 和 sidebar 角度）

输出：`output/daily/{date}.json`

### Step 07: 校验 JSON

生成后必须校验，不通过则修改后重新校验。

```bash
python3 scripts/validate_payload.py output/daily/{date}.json
```

→ 详见 `reference/pipeline/07_validate_payload.md`

### Step 08: 渲染 HTML

```bash
python3 scripts/render_daily.py output/daily/{date}.json --force
```

→ 详见 `reference/pipeline/08_render_html.md`

---

## 快速执行

```bash
DATE=$(date +%Y-%m-%d)

python3 scripts/build_queries.py --date $DATE --window 3
python3 scripts/collect_sources_with_opencli.py --date $DATE --max-keywords 5 --max-results 5
python3 scripts/filter_index.py --date $DATE --window 3
python3 scripts/collect_detail.py --date $DATE
python3 scripts/prepare_payload.py --date $DATE

# AI 生成 output/daily/$DATE.json

python3 scripts/validate_payload.py output/daily/$DATE.json
python3 scripts/render_daily.py output/daily/$DATE.json --force
```

→ 完整流水线说明见 `reference/pipeline/00_overview.md`

---

## 目录结构

```
config/
  profile.yaml              用户画像

scripts/
  build_queries.py           01 生成搜索查询
  collect_sources_with_opencli.py  02 采集候选池
  filter_index.py            03 时间筛选
  collect_detail.py          04 深抓正文
  prepare_payload.py         05 去噪打分
  validate_payload.py        07 校验 JSON
  render_daily.py            08 渲染 HTML
  render_index.py            站点首页生成
  feedback_server.py         反馈服务

reference/
  pipeline/                  流水线各步骤详细文档（8 个 .md）
  profile_template.yaml      profile 结构模板
  opencli_platforms.yaml     opencli 全量平台目录（31 个平台）
  opencli_output_formats.md  各平台输出字段和时间格式
  daily_collection_guide.md  采集执行指南
  daily_payload_example.json 日报 JSON 结构示例
  daily_example.html         HTML 视觉基线
  index_to_detail_guide.md   index → detail 流程说明

init/
  daily-init.md              画像初始化向导

output/
  daily/{date}.json          日报 JSON
  daily/{date}.html          日报 HTML
  raw/{date}_queries.txt     搜索查询
  raw/{date}_index.txt       原始候选池
  raw/{date}_index_filtered.txt  筛选后候选池
  raw/{date}_detail.txt      深抓详情
  raw/{date}_candidates.json 去噪打分后候选
  archive/                   旧 HTML 归档
```

---

## 工具依赖

### opencli（首选采集工具）

通过 Chrome DevTools Protocol 连接本地 Chrome，复用登录态采集 73+ 平台。

```bash
opencli doctor  # 检查连接状态
```

不可用时退回 `web_search` + `web_fetch`，不阻断生产。

### Python 3.10+

本地脚本依赖，pyyaml 用于解析 profile（无则用内置 parser）。

---

## 质量约束

- 前 3 条优先产品/模型/平台级变化
- 默认最近 3 天窗口
- URL 用具体文章页，不用首页
- 信号多样性：官方/媒体/社区/开源/研究
- 所有中间产物必须留痕到 `output/raw/`
- JSON 必须通过 `validate_payload.py` 校验后才能渲染

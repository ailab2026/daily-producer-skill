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

## Agent 执行契约

agent 使用本 skill 时，默认目标是**替用户端到端完成整条链路**，而不是只给建议、只做部分步骤、或停在分析阶段。

### 默认行为

1. 读取 `config/profile.yaml`
2. 若缺失或用户明确要求重建画像，按 `init/daily-init.md` 完成初始化
3. 初始化完成后，立即执行 `python3 scripts/apply_detected_publish_config.py --json`
4. 若返回 `status = "needs_confirmation"`，才向用户确认公开目录
5. 若返回 `status = "applied"` 或 `status = "no_change"`，直接继续日报生产流程
6. 完成 Step 01-11，直到产出 HTML、完成发布、通知、并启动反馈服务，除非用户明确要求只跑其中某一步

### 最少打扰原则

以下情况之外，agent 不应额外让用户做选择：
- `apply_detected_publish_config.py --json` 返回 `status = "needs_confirmation"`
- 初始化流程里 `init/daily-init.md` 明确要求等待用户确认
- 某一步将产生非显然副作用，例如覆盖现有画像、覆盖用户显式填写的 `publish.*`

### 完成判定

只有满足以下条件，才算“日报流程已完成”：
- `output/daily/{date}.json` 存在
- `output/daily/{date}.html` 存在
- 若启用了 publish：`output/publish/{date}.json` 存在，且公开目录中的 HTML 已写入
- 若启用了飞书通知：`send_feishu_card.py --date {date}` 已执行成功，或明确记录失败原因
- `feedback_server.py` 已启动，或明确记录未启动原因

### 禁止行为

- 不要只生成 `queries` / `index` 就结束
- 不要只渲染本地 HTML 而跳过 publish / notify
- 不要因为 publish 配置为空就直接让用户自己手填，必须先尝试自动探测
- 不要把 `server.public_url` 当成唯一公网地址真相，通知必须优先读取发布状态

---

## 运行时指令：用户提供信息源

用户在对话中提到某个网站、账号、平台或 URL，想纳入日报采集范围时，agent 必须正确写入 `config/profile.yaml`，而不是仅在本次临时使用。

### 判断类型并写入对应字段

**情况一：网站 / 媒体 / 官方博客**（有 URL，无 opencli 适配器）
→ 写入 `sources.websites.cn` 或 `sources.websites.global`

```yaml
sources:
  websites:
    global:
      - name: "The Verge AI"
        url: "https://www.theverge.com/ai-artificial-intelligence"
        type: "media"       # media | official | community
```

**情况二：直达 URL**（每次必看的固定页面，跳过搜索直接抓取）
→ 写入 `sources.direct`

```yaml
sources:
  direct:
    - "https://openai.com/news/"
    - "https://www.anthropic.com/news"
```

**情况三：有 opencli 适配器的平台**（微博/知乎/Twitter/Reddit 等）
→ 写入 `sources.platforms.cn` 或 `sources.platforms.global`，参考 `reference/opencli_platforms.yaml` 确认平台名

```yaml
sources:
  platforms:
    cn:
      - name: "小红书"
        opencli: "xiaohongshu"
        commands:
          - "search \"{keyword}\" --limit 10"
        login_required: yes
```

### 操作流程

1. 读取当前 `config/profile.yaml`
2. 判断类型，写入对应字段（追加，不覆盖已有内容）
3. 告知用户"已添加到 profile.yaml，下次生成日报时生效"
4. 若用户希望**立即生效**（本次日报也包含），在 Step 02 采集时额外处理该来源

**禁止：** 仅在对话中记住该来源而不写入 profile.yaml；禁止覆盖已有的 sources 列表。

---

## 生产流水线

共 11 步。步骤 01-05、07-09 有自动化脚本，步骤 06 由 AI 执行，步骤 00 和 10 为 feedback 系统集成。

**每步的详细说明、参数、输入输出格式见 `reference/pipeline/` 目录。**

```
profile.yaml
    ↓
00  【读取历史 feedback】       自动加载前一天 data/feedback/{date}.json
    ↓
01  build_queries.py           生成搜索查询
    ↓
02  collect_sources_with_opencli.py  采集候选池
    ↓
03  filter_index.py            时间筛选
    ↓
04  collect_detail.py          深抓正文
    ↓
05  prepare_payload.py         去噪打分（自动读取 feedback 加权）
    ↓
06  【AI】                     生成日报 JSON
    ↓
07  validate_payload.py        校验 JSON
    ↓
08  render_daily.py            渲染 HTML
    ↓
09  publish_daily.py           发布到公开目录并写发布状态
    ↓
10  send_feishu_card.py        飞书卡片通知（交互卡片，禁止降级为纯文本）
    ↓
11  feedback_server.py         启动反馈服务（后台，保持运行）
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

AI 读取 `output/raw/{date}_candidates.json`，从候选中选出 15 条目标条目，写 summary/relevance/sidebar，生成日报 JSON。

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
python3 scripts/render_daily.py output/daily/{date}.json --output output/daily/{date}.html --force
```

→ 详见 `reference/pipeline/08_render_html.md`

### Step 09: 发布日报

HTML 渲染完成后，先把日报复制到公开目录，并写入发布状态文件。

```bash
python3 scripts/publish_daily.py --date {date}
```

配置前提（在 `config/profile.yaml` 中）：
```yaml
publish:
  target_dir: "output/rwa/daily"
  public_base_url: "http://your-domain.com"
  public_daily_path: "/daily"
```

如果用户没有明确填写，agent 应先尝试自动推断：
- 已存在 `output/rwa/daily` / `output/public/daily` 等常见目录 → 自动作为 `publish.target_dir`
- `publish.public_base_url` 留空但 `server.public_url` 已配置 → 自动复用
- `publish.public_daily_path` 留空 → 根据 `target_dir` 相对 `output/` 的路径推断（如 `output/rwa/daily` → `/rwa/daily`）

可直接运行：

```bash
python3 scripts/detect_publish_config.py --json
```

若返回 `needs_confirmation.target_dir = true`，说明存在多个候选目录，才需要向用户确认。

初始化时，推荐直接调用：

```bash
python3 scripts/apply_detected_publish_config.py --json
```

返回值可直接驱动 agent 分支：
- `status = "applied"`：已自动写回
- `status = "no_change"`：当前配置已可用
- `status = "needs_confirmation"`：需要向用户确认候选目录

默认只补空值，不覆盖用户已填写的 `publish.*`；只有在确实需要用环境探测结果覆盖现有值时，才使用 `--force`。

### Step 10: 飞书卡片通知

发布成功后，再向飞书群发送**交互卡片**（`msg_type: interactive`）。

```bash
python3 scripts/send_feishu_card.py --date {date}
```

**格式强制要求：** 必须使用交互卡片，禁止降级为纯文本。飞书机器人发的纯文本消息没有链接预览；只有 `msg_type: interactive` 才能显示带标题和按钮的卡片。

通知会优先读取 `output/publish/{date}.json` 中的公开 URL；如果配置了 `publish` 但尚未发布，会直接报错，避免发出 404 链接。

配置前提（在 `config/profile.yaml` 中）：
```yaml
publish:
  public_base_url: "http://your-domain.com"
  public_daily_path: "/daily"
feishu:
  notification:
    enabled: true
    chat_id: "oc_xxx"
```

→ 详见 `reference/pipeline/09_notify_feishu.md`

---

## 共享部署初始化

共享出去后，推荐在首次生成日报前先跑下面这组最小命令：

```bash
# 1. 先按 init/daily-init.md 完成画像初始化，生成 config/profile.yaml

# 2. 自动补全 publish 配置；只有 status=needs_confirmation 时才需要继续问用户
python3 scripts/apply_detected_publish_config.py --json

# 3. 确认 agent 将返回结果写回或已保持现状，然后再生成日报
DATE=$(date +%Y-%m-%d)
python3 scripts/build_queries.py --date $DATE --window 3
```

推荐判断规则：
- 返回 `status = "applied"`：说明 `publish.*` 已自动写入 `config/profile.yaml`
- 返回 `status = "no_change"`：说明当前环境已有可用发布配置
- 返回 `status = "needs_confirmation"`：说明存在多个候选公开目录，这时再问用户

---

## 快速执行

```bash
DATE=$(date +%Y-%m-%d)

# Step 00: feedback 由 prepare_payload.py 自动读取，无需手动操作

python3 scripts/build_queries.py --date $DATE --window 3
python3 scripts/collect_sources_with_opencli.py --date $DATE --max-keywords 5 --max-results 5
python3 scripts/filter_index.py --date $DATE --window 3
python3 scripts/collect_detail.py --date $DATE
python3 scripts/prepare_payload.py --date $DATE   # 自动读取前一天 feedback 加权

# AI 生成 output/daily/$DATE.json

python3 scripts/validate_payload.py output/daily/$DATE.json
python3 scripts/render_daily.py output/daily/$DATE.json --output output/daily/$DATE.html --force

# Step 09: 发布到公开目录
python3 scripts/publish_daily.py --date $DATE

# Step 10: 飞书卡片通知（必须用卡片，不得用纯文本）
python3 scripts/send_feishu_card.py --date $DATE

# Step 11: 启动反馈服务（同时自动启动 graphify watch，如果 profile 中已启用）
nohup python3 scripts/feedback_server.py >> output/server.log 2>&1 &
```

### Step 11 说明（反馈服务）

- 用 `nohup` 启动，会话关闭不受影响
- 端口被占时明确报错（不再静默漂移到 +1 端口）
- 自动 24 小时后退出（可在 `config/profile.yaml` 的 `server.timeout_hours` 调整）
- 日志写入 `output/server.log`
- 若服务已在运行，`feedback_server.py` 会自动关闭旧进程再重启

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
  publish_daily.py           09 发布日报
  send_feishu_card.py        10 飞书卡片通知（交互卡片，禁止纯文本）
  render_index.py            站点首页生成
  feedback_server.py         11 反馈服务

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

### Graphify（可选，知识图谱收藏功能）

日报中的「收藏」按钮依赖 Graphify 将文章写入本地知识图谱。**首次使用前必须安装并启动 watch 模式：**

```bash
pip install graphifyy

# 启动 watch 模式（后台持续监听新收藏）
graphify ~/graphify-data --watch &
```

启动后，用户在日报中点击收藏 → 文章自动写入 `~/graphify-data/raw/` → Graphify 增量更新知识图谱。

**开启方式：** 在 `config/profile.yaml` 中设置：
```yaml
graphify:
  enabled: true
  data_dir: "~/graphify-data"   # 与上方 graphify 命令路径保持一致
```

不需要此功能可跳过（`enabled: false` 时收藏按钮不写入文件，点击无副作用）。

---

## 质量约束

- 前 3 条优先产品/模型/平台级变化
- 默认最近 3 天窗口
- URL 用具体文章页，不用首页
- 信号多样性：官方/媒体/社区/开源/研究
- 所有中间产物必须留痕到 `output/raw/`
- JSON 必须通过 `validate_payload.py` 校验后才能渲染

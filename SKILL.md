---
name: daily-producer
description: End-to-end daily report production engine — from user profile check, feedback loading, multi-source candidate collection, detail deep-fetch, structured payload generation, HTML rendering, to site publishing and feedback loop. Use when generating, regenerating, or managing the personalized AI daily report pipeline.
---

# Daily Producer Skill

从画像、反馈、采集、成稿、渲染到发布的完整闭环日报生产系统。

## 角色定位

本 skill 是日报系统中的**唯一正式生产与发布引擎**。

负责：
1. 检查并读取用户画像 (`config/profile.yaml`)
2. 读取最近 7 天反馈
3. 执行资讯采集（两路并行：来源直扫 + 查询搜索）
4. 筛选、排序、分级、个性化解读
5. 产出结构化日报 JSON (`output/daily/{date}.json`)
6. 渲染日报 HTML (`output/daily/{date}.html`)
7. 生成站点首页 (`output/index.html`)
8. 维护正式公网输出目录 (`output/`)
9. 按需提供本地反馈服务

不负责：
- 不直接对外回复用户
- 不让调用方替它做 query / 来源 / 排序判断
- 不做日报质量评分

---

## 日报启动协议（强制）

当用户表达“生成日报 / 进入流程 / 跑 daily / 生成今天的日报”这类意图时，必须先完成以下入口检查，再决定是否进入初始化。

### Mandatory Preflight

1. **必须先读取 `config/profile.yaml`**
2. 根据读取结果严格分流：
   - **不存在** → 必须先读取并遵循 `init/daily-init.md`，进入初始化流程
   - **存在** → 直接使用现有 profile，继续日报生产流程
3. **只有以下两种情况允许向用户发起初始化相关提问：**
   - `config/profile.yaml` 不存在
   - 用户明确要求“重新初始化 / 重建画像 / daily-init”

### 禁止行为

- 未读取 `config/profile.yaml` 就先问用户“你关注什么”“你想看什么”
- 仅因为用户说“进入流程”就默认进入初始化
- 把“生成日报”和“初始化画像”视为同一入口
- 在 `config/profile.yaml` 已存在且用户未要求重建时，主动触发初始化对话

## 执行流程

```
check_profile
→ load_recent_feedback
→ collect_index_candidates
→ collect_detail_for_selected
→ compose_payload_json
→ render_daily_html
→ render_site_index
→ serve_from_output_root
```

### Step 1: check_profile

检查 `config/profile.yaml` 是否存在。

- **文件不存在** → 必须先读取并遵循 `init/daily-init.md`，进入初始化流程，**不跳过、不自行概括、不允许仅凭本文件摘要执行初始化**
- **文件存在** → 直接读取使用，继续后续步骤

**强制执行约束：**
1. 一旦发现 `config/profile.yaml` 不存在，调用方必须先读取 `init/daily-init.md` 原文，再继续。
2. 在 `init/daily-init.md` 被读取之前，不得提前向用户发起初始化问题，不得自行压缩为一次性问卷。
3. 如果 `init/daily-init.md` 规定为逐步提问，则必须一问一答推进；每次只提出当前步骤要求的一个问题或一个确认动作，等待用户回复后再进入下一步。
4. 只有在 `init/daily-init.md` 明确允许的情况下，才能把多个信息点合并为一次提问。

初始化流程按 `init/daily-init.md` 与 `reference/profile_template.yaml` 模板共同执行，不能只参考其中之一。

### Step 2: load_recent_feedback

读取 `data/feedback/` 下最近 7 天的 `{date}.json`。

反馈影响：
- 候选排序加权
- 条目解释角度
- 行动建议方向
- 中英文来源比例

无反馈时：允许继续，标记 `feedback_status: missing`, `personalization_limit: true`。

### Step 3: collect_index_candidates

建立候选池，默认时间窗口最近 3 天。

**两路并行采集：**

A. **来源直扫** — 扫描 `sources.cn` / `sources.global` 中配置的来源
B. **查询搜索** — 按 `query_profiles` 中 topic 对应的 cn/global 模板主动检索

合并去重后写入 `output/raw/{date}_index.txt`。

**工具优先级：**
1. 首选：`opencli`（平台原生采集 — 社交媒体搜索/热榜、网页抓取、Google 搜索）
2. 退回：`web_search`（标题/链接/摘要搜索）
3. 退回：`web_fetch`（URL 验证、正文补抓）

发生 fallback 必须在 raw 中写明 `fallback_reason`。

**候选记录字段：** 来源名、标题、URL、发布时间、命中 topic、命中关键词、信号类型（官方/社区/媒体/开源）、初步判断。

**固定来源：** 中文固定源（微博、B站、小红书、微信社区）、Global 固定源（Reddit、X），同时覆盖 profile 中其余来源。

**初筛规则：**
- 保留：最近3天、与画像强相关、有明确链接、属于官方更新/产品变化/社区热议/开源生态/行业变化
- 排除：与画像无关、旧闻翻炒、纯营销稿、无链接转述、纯情绪讨论

### Step 4: collect_detail_for_selected

对高价值候选做 detail 深抓。进入条件：
- 对画像有明显影响
- 排名进入当日前列
- 能代表趋势/动作建议/重要变化
- 来源可信

补齐：完整事实、准确日期、链接可靠性、交叉验证。

每条判断为 `selected` / `background_only` / `discarded`。

留痕写入 `output/raw/{date}_detail.txt`。

### Step 5: compose_payload_json

产出 `output/daily/{date}.json`，满足渲染器契约。

顶层结构：
```json
{
  "meta": { "date": "", "date_label": "", "role": "" },
  "raw_capture_path": "",
  "left_sidebar": {
    "overview": [],
    "actions": [],
    "trends": { "rising": [], "cooling": [], "steady": [], "insight": "" }
  },
  "articles": [],
  "data_sources": []
}
```

单条 article 结构：
```json
{
  "id": "",
  "title": "",
  "priority": "major|normal|minor",
  "time_label": "",
  "source_date": "",
  "source": "",
  "url": "",
  "summary": { "what_happened": "", "why_it_matters": "" },
  "relevance": "",
  "tags": [],
  "credibility": { "source_tier": "", "confidence": "", "cross_refs": 0, "sources": [] }
}
```

原则：
- `meta.date` 必须为真实目标日期
- `time_label` 尽量具体
- `summary` 同时说明发生了什么 + 为什么重要
- `relevance` 说明与画像/用户工作的关系
- 前 3 条优先产品/模型/平台级变化

### Step 6: render_daily_html

调用 `scripts/render_daily.py`，读取 payload JSON，输出 `output/daily/{date}.html`。
若旧 HTML 存在，先归档到 `output/archive/`（命名 `{year-month-day-hour-min}.html`）。

页面包含：顶部 header、左侧栏（速览/行动建议/趋势雷达）、右侧文章卡片流、页脚数据来源、反馈与 AI 交互脚本。

视觉基线参考：`reference/daily_example.html`。

### Step 7: render_site_index

调用 `scripts/render_index.py`，扫描 `output/daily/*.json`，重建 `output/index.html`。

### Step 8: serve_from_output_root

`output/` 是正式对外站点根目录，80 端口静态服务应直接指向此目录。

---

## 目录结构

```
config/                 # 画像与执行配置
  profile.yaml          # 用户画像（必须完整才能生产）
  example-profile.yaml  # 结构模板参考
scripts/                # 执行脚本
  render_daily.py       # 单日报 HTML 渲染器（运行时真相）
  render_index.py       # 首页生成器
  feedback_server.py    # 反馈服务
  build_queries.py      # 查询构建
  archive_previous_daily.py
  save_raw_capture.py
  check_source_health.py
  track_source_signals.py
  open_daily.py
  apply_source_changes.py
reference/              # 参考文件
  daily_example.html    # 日报页视觉与交互基线
  daily_payload_example.json
  profile_template.yaml
  daily_collection_guide.md
  raw_capture_example.txt
  feedback_schema.json
init/                   # 初始化流程
  daily-init.md          # 画像检查 + 初始化向导（合并）
  daily-init.md
output/                 # 正式产出目录（对外展示根目录）
  daily/{date}.json     # 结构化日报
  daily/{date}.html     # 日报 HTML
  index.html            # 站点首页
  raw/{date}_index.txt  # 候选池留痕
  raw/{date}_detail.txt # 深抓留痕
  archive/              # 旧 HTML 归档
data/
  feedback/{date}.json  # 用户反馈数据
```

---

## 质量约束

- 前 3 条优先产品/模型/平台级变化
- 默认最近 3 天窗口，更早信息仅作背景
- URL 用具体文章页，不用首页替代
- 保持信号多样性：官方/媒体/社区/开源/研究
- 候选池必须留痕，不仅保留最终入选条目
- payload 必须满足渲染器契约
- `reference/daily_example.html` 是样式基线，修改页面风格先改它再同步渲染器

---

## 协作边界

- 调用方只做路由、串联、汇总与回复
- 以下判断由本 skill 自己完成，不推回给调用方：
  - query 怎么生成
  - 候选来源怎么选
  - 哪些条目入选 / 进前 3
  - 哪条更适合用户
  - 页面应重建哪些输出物

---

## 输出要求

返回结构化结果，至少说明：
- 是否成功
- 目标日期
- 使用的 profile / feedback 情况
- raw 留痕文件位置
- 生成的 JSON / HTML 路径
- 是否启动反馈服务及访问地址
- 若失败，明确卡在哪一步

---

## 画像初始化引导

当 profile 不可用时，不跳过，而是引导初始化。

**这里是摘要，不是初始化流程正文。真正执行时必须读取 `init/daily-init.md`。**

执行约束：
1. 不得仅依据本节摘要直接开始提问。
2. 必须先读取 `init/daily-init.md`，再按其中步骤执行。
3. 如果 `init/daily-init.md` 与本节摘要有差异，以 `init/daily-init.md` 为准。
4. 若 `init/daily-init.md` 要求逐步提问，则严禁一次性抛出多个问题。

摘要目标：
1. 先问用户关心什么，不问看哪些站
2. 按角色推荐来源模板（cn/global 分层）
3. 自动补齐 topics → keywords → query_profiles → collection_contract
4. 用户只需回答：关心什么、不关心什么、特别想看的平台、中文优先还是全球优先
5. 参考 `config/example-profile.yaml` 作为结构骨架
6. 写回 `config/profile.yaml`

---

## 工具依赖

### 核心外部依赖：opencli

`opencli`（`@jackwener/opencli`）是本 skill 的首选采集工具。它通过 Chrome DevTools Protocol (CDP) 连接本地已登录的 Chrome 浏览器，复用登录态，支持 73+ 平台的结构化数据采集，**零 API Key、零 LLM 运行时成本**。

#### 检查是否已安装

```bash
# 快速检查
opencli --version && opencli doctor
```

正常应显示版本号，且 doctor 输出 Daemon、Extension、Connectivity 三项均为 `[OK]`。

#### 安装方法

```bash
# 1. 安装 opencli
npm install -g @jackwener/opencli

# 2. 启动虚拟显示 + Chrome（服务器无桌面环境时）
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99
google-chrome --no-sandbox --disable-gpu --display=:99 \
  --remote-debugging-port=9222 \
  --user-data-dir=/root/chrome-profile \
  --window-size=1280,800 &

# 3. 安装并加载 Browser Bridge 扩展
cd /usr/lib/node_modules/@jackwener/opencli/extension && npm install && npm run build
# 在 Chrome 中加载扩展（chrome://extensions/ → Load unpacked → 扩展目录）

# 4.（可选）启动 noVNC 用于远程登录网站
apt-get install -y x11vnc novnc websockify
x11vnc -display :99 -nopw -forever -shared -bg
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
# 通过 http://localhost:6080/vnc.html 登录目标网站
```

#### 验证安装

```bash
opencli doctor
```

应输出：
```
[OK] Daemon: running on port 19825
[OK] Extension: connected (v1.5.5)
[OK] Connectivity: connected
```

#### 支持的平台与采集命令

| 来源类型 | 平台 | opencli 命令 | 是否需要登录 |
|---------|------|-------------|-------------|
| 社交媒体 | Twitter/X | `opencli twitter search/notifications/profile` | 是 |
| 社交媒体 | 微博 | `opencli weibo hot/search/feed` | hot 不需要，其余需要 |
| 社交媒体 | 小红书 | `opencli xiaohongshu search/feed/note` | 是 |
| 视频 | B站 | `opencli bilibili hot/search/ranking` | 部分需要 |
| 技术社区 | HackerNews | `opencli hackernews` | 否 |
| 技术社区 | Reddit | `opencli reddit` | 否 |
| 技术社区 | V2EX | `opencli v2ex` | 否 |
| 学术 | arXiv | `opencli arxiv search/paper` | 否 |
| 新闻 | BBC | `opencli bbc news` | 否 |
| 新闻 | Bloomberg | `opencli bloomberg` | 部分需要 |
| 开发者 | GitHub | `opencli gh`（外部 CLI 透传） | 否 |
| 知识 | 知乎 | `opencli zhihu` | 是 |
| 搜索引擎 | Google | `opencli google search/news/trends` | 否 |
| 通用网页 | 任意 URL | `opencli web read --url <URL>` | 否 |
| 中文媒体 | 机器之心 | `opencli google search "site:jiqizhixin.com <关键词>"` + `opencli web read --url <文章URL>` | 否 |
| 中文媒体 | 量子位 | `opencli google search "site:qbitai.com <关键词>"` + `opencli web read --url <文章URL>` | 否 |

#### 运行时检查（采集前自动执行）

在进入 `collect_index_candidates` 之前，skill 应自动执行以下检查：

```bash
# 检查 opencli 是否可用
if command -v opencli &>/dev/null; then
  opencli doctor 2>&1
  echo "opencli: available"
else
  echo "opencli: NOT available — will fallback to web_search + web_fetch"
fi
```

若 opencli 不可用：
- **不阻断生产**，退回 `web_search` + `web_fetch`
- 在 raw 留痕中写明 `fallback_reason: opencli not available`
- 在最终结果中标记平台覆盖能力受限

若 opencli 可用但某平台未登录（返回 `🔒 Not logged in`）：
- 对该平台退回 `opencli google search "site:<平台域名> <关键词>"` 间接采集
- 在 raw 留痕中写明 `fallback_reason: <平台> not logged in, used google site: search`

### 内置工具（无需额外安装）

- `web_search`：fallback 搜索（Claude Code 内置）
- `web_fetch`：URL 验证与正文补抓（Claude Code 内置）

### 本地脚本

- `scripts/render_daily.py`：HTML 渲染
- `scripts/render_index.py`：首页生成
- `scripts/feedback_server.py`：反馈服务
- `scripts/build_queries.py`：查询构建
- `scripts/archive_previous_daily.py`：旧 HTML 归档
- `scripts/save_raw_capture.py`：原始采集保存
- `scripts/check_source_health.py`：来源健康检查
- `scripts/track_source_signals.py`：来源信号追踪

### Python 依赖

本地脚本依赖 Python 3.10+，无额外第三方包要求（均使用标准库）。

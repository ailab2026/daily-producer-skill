# 06 AI 生成日报 JSON

## 无脚本，由 AI 执行

这一步没有自动化脚本，由 AI 读取 candidates.json + profile.yaml，生成最终日报 JSON。

## 输入

- `output/raw/{date}_candidates.json` — 由 prepare_payload.py 生成的结构化候选
- `config/profile.yaml` — 用户画像（role、role_context、topics）
- `reference/daily_payload_example.json` — JSON 结构示例

## 输出

- `output/daily/{date}.json` — 符合渲染器契约的日报 JSON

## AI 需要做的事

### 1. 从候选中选出 max_items 条（默认 15）

**选择标准：**
- 跳过明显噪音（如 "Agent" 指经纪人/执法人员的非 AI 内容）
- 同一事件在多平台出现 → 合并为一条，记录多源交叉验证
- 优先选择：官方发布 > 高热度社区讨论 > 媒体深度报道 > 背景信息
- 确保 topics 覆盖（不要全是同一个话题）

**优先级分配：**
- `major`（2-3 条）：本周最重要的事件，产品/模型/平台级变化
- `notable`（3-5 条）：值得关注但影响范围较小
- `normal`（5-7 条）：有价值的信息
- `minor`（0-2 条）：背景信息或趋势信号

### 2. 为每条写 summary

```json
"summary": {
  "what_happened": "发生了什么（事实描述，不加观点）",
  "why_it_matters": "为什么重要（对行业/用户的影响）"
}
```

### 3. 为每条写 relevance

一句话说明与用户画像（role + role_context）的关系。

### 4. 生成 left_sidebar

- **overview**（3 条）：今日最重要的 3 个信号，每条含 title + text
- **actions**（3-4 条）：行动建议，每条含 type（learn/try/watch/alert）、text、prompt
- **trends**：rising/cooling/steady 各 3-4 个词，insight 一句话总结

### 5. 填写 credibility

```json
"credibility": {
  "confidence": "high/medium/low",
  "source_tier": "tier-1/tier-2",
  "cross_refs": 3,
  "evidence": "来源说明",
  "sources": [{"name": "xxx", "url": "xxx"}]
}
```

- 多源交叉验证 → confidence: high
- 单源但来源可信 → confidence: medium
- 泄露/未确认 → confidence: low

## JSON 结构

必须严格遵循 `reference/daily_payload_example.json` 的结构。核心字段：

```json
{
  "meta": {"date": "", "date_label": "", "role": ""},
  "tools": [...],
  "left_sidebar": {
    "overview": [{"title": "", "text": ""}],
    "actions": [{"type": "", "text": "", "prompt": ""}],
    "trends": {"rising": [], "cooling": [], "steady": [], "insight": ""}
  },
  "articles": [{
    "id": "", "title": "", "priority": "", "time_label": "",
    "source_date": "", "source": "", "url": "",
    "summary": {"what_happened": "", "why_it_matters": ""},
    "relevance": "", "tags": [],
    "credibility": {"confidence": "", "source_tier": "", "cross_refs": 0}
  }],
  "data_sources": []
}
```

## 强制规则

1. **禁止使用假 URL**：所有 `url` 和 `credibility.sources[*].url` 必须从 candidates.json 中的真实 URL 复制，不得编造（如 `https://weibo.com/example/xxx`）
2. **多源合并时保留所有原始 URL**：同一事件在多平台出现时，主 `url` 用最重要来源的 URL，其余放入 `credibility.sources` 数组
3. **cross_refs 必须有依据**：`cross_refs` 数值必须等于 `credibility.sources` 数组的长度，不能写一个数字但没列出来源
4. **没有 URL 就不写**：如果 candidates.json 中某条没有 url，对应 article 的 url 字段写空字符串，不要编造

## 生成后

**必须运行 validate_payload.py 校验**，通过后才能渲染 HTML。

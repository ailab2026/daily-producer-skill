# 07 校验 JSON

## 脚本

```bash
python3 scripts/validate_payload.py output/daily/{date}.json
```

## 作用

校验 AI 生成的日报 JSON 是否符合渲染器契约。**必须在渲染 HTML 之前运行。**

## 输入

- `output/daily/{date}.json` — AI 生成的日报 JSON

## 输出

- 通过：`✅ 校验通过` + 统计信息
- 失败：`❌ 校验失败` + 具体错误列表

## 校验项

### meta（必需）

- `date`：非空，格式 YYYY-MM-DD
- `date_label`：非空
- `role`：非空

### left_sidebar（必需）

- `overview`：数组，至少 2 条，每条有 title + text
- `actions`：数组，至少 2 条，每条有 text + prompt，type 必须是 learn/try/watch/alert 之一
- `trends`：有 rising/cooling/steady（均为数组）+ insight（字符串）

### articles（必需）

- 数组，至少 5 条
- 每条必须有：id（唯一）、title、priority、source、url
- priority 必须是：major/notable/normal/minor
- summary 必须有 what_happened + why_it_matters
- relevance 非空
- tags 是数组
- url 以 http 开头

### data_sources（必需）

- 非空数组

## 失败处理

如果校验失败：

1. 阅读错误列表
2. 修改对应字段
3. 重新运行校验
4. 直到通过后才能进入渲染步骤

示例错误输出：

```
❌ 校验失败，3 个错误：
   [meta.date_label] 缺失或为空
   [articles[2].summary.why_it_matters] 缺失
   [articles[5].url] 格式错误: example.com/...
```

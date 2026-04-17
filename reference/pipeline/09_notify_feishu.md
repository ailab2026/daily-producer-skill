# 09 飞书卡片通知

## 脚本

```bash
python3 scripts/publish_daily.py --date <date>
python3 scripts/send_feishu_card.py --date <date> [<chat_id>]
```

## 作用

日报 HTML 渲染完成后，先执行发布，再向飞书群发送一条**交互卡片消息**，卡片包含：

- 标题：📰 AI 日报 · {日期}（蓝色 header）
- 正文：今日 AI 情报已生成，点击下方按钮查看完整日报。
- 按钮：「打开今日日报」→ 链接到日报 HTML 页面

## 为什么必须用卡片（禁止用纯文本）

飞书机器人发送的 `text` 类型消息不会自动抓取 OG 预览卡片；只有用户自己发的消息才有 URL 预览。
使用 `msg_type: interactive`（交互卡片）是让机器人通知显示链接预览的**唯一正确方式**。

**严禁将通知格式降级为纯文本。**

## 输入

- `date`：日报日期。`send_feishu_card.py --date` 会优先读取 `output/publish/{date}.json` 中的公开 URL
- `chat_id`（可选）：飞书群 ID（oc_xxx）。未提供时从 `config/profile.yaml` 的 `feishu.notification.chat_id` 读取

## 配置

在 `config/profile.yaml` 中配置：

```yaml
publish:
  target_dir: "output/rwa/daily"         # 公开目录
  public_base_url: "http://your-domain.com"
  public_daily_path: "/daily"

feishu:
  notification:
    enabled: true
    chat_id: "oc_xxx"                    # 飞书群 ID（必填）
    # 格式固定为交互卡片，不可修改为纯文本
```

如果这些字段未显式填写，系统会优先自动推断：
- 已存在常见公开目录时自动识别 `target_dir`
- `public_base_url` 留空时回退到 `server.public_url`
- `public_daily_path` 留空时按 `target_dir` 相对 `output/` 的路径推断

凭据从 `/root/.openclaw/openclaw.json` 读取（使用 `channels.feishu.accounts[defaultAccount]` 的 appId + appSecret）。

## 完整示例

```bash
DATE=$(date +%Y-%m-%d)
python3 scripts/publish_daily.py --date "$DATE"
python3 scripts/send_feishu_card.py --date "$DATE"
```

或直接指定 URL：

```bash
python3 scripts/send_feishu_card.py http://intelligenceassistant.online/daily/2026-04-15.html
```

## 缺失提醒（日报未生成时）

```bash
python3 scripts/send_feishu_card.py --text "今日 AI 日报尚未产出，请检查 daily-producer 的生成链路。"
```

## 定时任务配置（cron job）

如果通过 OpenClaw 定时任务推送通知，使用以下配置：

```json
{
  "delivery": { "mode": "none" },
  "payload": {
    "message": "运行 python3 scripts/send_feishu_card.py <url> <chat_id> 发送卡片通知，不要输出文本让系统转发（delivery.mode 已设为 none）"
  }
}
```

`delivery.mode` 必须设为 `"none"`，否则系统会额外把 agent 的文本响应作为纯文本发送，造成重复消息。

## 失败保护

- 若 `publish` 已配置，但 `output/publish/{date}.json` 不存在，`send_feishu_card.py --date` 会直接报错
- 若发布状态存在但目标文件不存在，也会报错
- 这样可以避免“本地已生成，但未发布，飞书仍发出 404 链接”的问题

## 防重复发送

agent 负责维护状态文件，记录每天已发送的 URL，避免同一 URL 重复发送。状态文件路径由 agent 自定义（通常在 workspace/state/ 下）。

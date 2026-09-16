---
name: podcast-weekly-collector
description: 按指定自然周从公开 RSS 采集播客单集元信息，并按 RSS 逐字稿、公开节目页、公开音频 ASR 的优先级取得逐字稿。用于播客周采集、单集发现、逐字稿来源定位和 ASR 前置准备；不绕过登录、付费墙、robots 限制或访问控制。
---

# 播客周采集

从用户提供的 RSS 清单中筛选指定时间区间内的单集，并为后续逐字稿清洗建立可追溯目录。

## 输入

- `sources.json`：节目 ID、名称和公开 RSS URL。默认跟踪清单见 [`assets/default-sources.json`](assets/default-sources.json)，当前包含 11 个公开来源。
- `--start`：含时区的区间起点，包含。
- `--end`：含时区的区间终点，不包含。
- 输出目录：用于保存 manifest、RSS、单集元信息与原始节目简介。

示例配置见 [`references/input-schema.md`](references/input-schema.md)。

## 采集顺序

对每个区间内单集依次执行：

1. **RSS 显式逐字稿**：识别 Podcasting 2.0 `podcast:transcript` 等公开字段，记录 URL、MIME 类型和语言。
2. **公开节目页**：只读取无需登录即可访问的可见内容，查找全文逐字稿或明确指向逐字稿的链接；简介和 Shownotes 不能冒充逐字稿。
3. **公开音频 ASR**：前两步均无全文时，使用 RSS enclosure 中的公开音频。ASR 通道应返回起止时间、正文、置信度，并尽可能返回 speaker。

不得绕过登录、付费墙、验证码、robots 限制或站点访问控制。页面无法公开访问时，记录原因并进入下一合法通道。

## 确定性 RSS 采集

```bash
python3 <skill-dir>/scripts/fetch_week.py \
  --sources <skill-dir>/assets/default-sources.json \
  --start <ISO-8601> \
  --end <ISO-8601> \
  --output <output-dir>
```

脚本只负责公开 RSS 下载、日期筛选、字段提取和目录生成，不调用私有 ASR 服务。

## ASR 输出契约

外部 ASR 结果规范化为：

```json
[
  {
    "start_time": 0.0,
    "end_time": 4.2,
    "speaker": "1",
    "text": "……",
    "confidence": 0.97
  }
]
```

将其保存为 `episodes/<episode_id>/transcript/segments.raw.json`。没有 speaker 或 confidence 时省略字段，不填造默认值。

## 证据与状态

每集至少保存：

- `metadata.json`：节目、标题、日期、节目页、音频 URL、时长和逐字稿候选。
- `shownotes.raw.txt`：RSS 原始简介，仅作章节与身份核对证据。
- `transcript/segments.raw.json`：ASR 或公开逐字稿的原始结构化结果。
- `transcript/transcript.meta.json`：取得通道、时间、来源 URL、状态和质量字段。

推荐状态：

- `rss_transcript_found`
- `web_transcript_found`
- `asr_required`
- `asr_transcript_generated`
- `manual_review_required`
- `unavailable`

## 质量门槛

风险只标记，不删除或伪装结果：

- 检查时间戳单调性、空文本、时长覆盖、speaker 缺失和置信度。
- 标题、节目、日期或音频身份冲突时使用 `manual_review_required`。
- 逐字稿可继续进入清洗 Skill，但必须保留风险标记和原始证据。

## 输出目录

```text
<output-dir>/
├── manifest.json
├── rss/
├── source-status/
└── episodes/
    └── <episode_id>/
        ├── metadata.json
        ├── shownotes.raw.txt
        └── transcript/
```

## 完成检查

- 日期筛选遵循 `[start, end)`。
- 单集 ID 稳定，可重复运行。
- 来源 URL 与跳转后 URL 均可追溯。
- Shownotes 未被误标为逐字稿。
- 不包含 cookie、token、账号信息或本地绝对路径。

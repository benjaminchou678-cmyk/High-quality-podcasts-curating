---
name: podcast-weekly-collector
description: 按指定自然周从公开 RSS 采集播客单集元信息，并按 RSS 逐字稿、公开节目页、飞书妙记、通用 ASR 备选的优先级取得逐字稿；进入逐字稿生成前主动询问用户选择输出为飞书文档、Markdown 文件或两者。用于播客周采集、单集发现、妙记转写、逐字稿来源定位和 ASR 备选准备；不绕过登录、付费墙、robots 限制或访问控制。
---

# 播客周采集

从用户提供的 RSS 清单中筛选指定时间区间内的单集，并为后续逐字稿清洗建立可追溯目录。

## 输出选择与下游交付

RSS 元数据和来源状态可以先采集，但在开始取得/清洗逐字稿或创建最终周报前，检查用户是否明确输出载体。

- 未明确时主动询问：`本次逐字稿和周报希望输出为：A. 飞书文档；B. Markdown 文件；C. 两者都要？`
- 记录 `output_targets`：`lark_doc`、`markdown` 或二者组成的数组，并传递给逐字稿清洗 Skill。
- 选择飞书：调用清洗 Skill 的飞书分支，创建或原地更新逐字稿和周报。
- 选择 Markdown：调用清洗 Skill 的 Markdown 分支，生成可移植的逐字稿及周报 `.md`，不写飞书。
- 选择两者：基于同一内容同时生成，分别验证并交付。
- 用户已明确选择时不重复询问；批量单集继承同一选择。

## 输入

- `sources.json`：节目 ID、名称和公开 RSS URL。默认跟踪清单见 [`assets/default-sources.json`](assets/default-sources.json)，当前包含 23 个公开来源。
- `--start`：含时区的区间起点，包含。
- `--end`：含时区的区间终点，不包含。
- 输出目录：用于保存 manifest、RSS、单集元信息与原始节目简介。

示例配置见 [`references/input-schema.md`](references/input-schema.md)。

## 采集与转写顺序

对每个区间内单集依次执行：

1. **RSS 显式逐字稿**：识别 Podcasting 2.0 `podcast:transcript` 等公开字段，记录 URL、MIME 类型和语言。
2. **公开节目页**：只读取无需登录即可访问的可见内容，查找全文逐字稿或明确指向逐字稿的链接；简介和 Shownotes 不能冒充逐字稿。
3. **飞书妙记主通道**：前两步均无全文时，使用 RSS enclosure 中的公开音频。先读取运行环境中的 `lark-drive` 与 `lark-meeting` Skill，再完整执行 [`飞书妙记工作流`](references/feishu-minutes-workflow.md)：下载音频、上传到原播客文件夹、创建一次妙记、等待转写、导入证据层、生成中文议题提要并写回妙记总结区。妙记只承担转写、说话人、时间戳和回听；原豆包逐字稿及周报仍归档到用户原先指定的“按播客/按周”文件夹。
4. **通用 ASR 备选通道**：仅当妙记不可用、超出限制、额度不足或明确失败时，才按 [`ASR 接入契约`](references/asr-contract.md) 调用原 ASR。不得同时启动妙记与 ASR，也不得因妙记失败把 Shownotes 当全文。

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

## 飞书妙记主通道与 ASR 备选

飞书妙记是没有公开全文时的默认音频转写通道。完整执行步骤、格式与大小限制、幂等、失败恢复、临时文件清理和原文件夹归档要求见 [`飞书妙记工作流`](references/feishu-minutes-workflow.md)。

妙记导出的逐字稿通过以下确定性脚本接回证据层：

```bash
python3 <skill-dir>/scripts/import_minutes_transcript.py \
  <transcript.txt> \
  <episode-dir> \
  --minute-url <minute_url> \
  --audio-file-url <audio_file_url>
```

脚本生成 `minutes.transcript.raw.txt`、`segments.raw.json` 和 `transcript.meta.json`，并将 `acquisition_method` 记录为 `feishu_minutes`。妙记一般提供时间戳和说话人，但不保证片段置信度；缺少置信度时按清洗 Skill 规则标记风险。

仅 Markdown 输出默认不使用会创建云端资源的妙记，除非用户单独授权。其他情况下妙记为默认音频转写通道，详见工作流。渲染总结时使用：

```bash
python3 <skill-dir>/scripts/render_minutes_summary.py \
  <episode-dir>/transcript/topic-digest.json \
  --output <episode-dir>/transcript/minutes-summary.md
```

与豆包文档共用一份中文提要；正文保持原语言。导入脚本拒绝覆盖原始证据，TXT 结束时间仅为推算边界，质量报告必须标记。归档目标来自私有 `archive_context`，不要猜文件夹或写到根目录。只取得正文但总结写回失败时继续归档，不重做 ASR。

通用 ASR 是运行环境提供的音频转写工具、模型或 API，不随 Skill 自动安装。仅在妙记通道不可用或失败时启用；首次使用前完整读取 [`ASR 接入契约`](references/asr-contract.md) 并用短音频实测。外部 ASR 结果规范化为：

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

将其保存为 `episodes/YYYY-MM-DD_节目名_简短标题/transcript/segments.raw.json`。完整 `episode_id` 只保存在元数据中；发生同名冲突时目录末尾追加 `episode_id` 前 6 位。没有 speaker 或 confidence 时省略字段，不填造默认值。

## 证据与状态

每集至少保存：

- `metadata.json`：节目、标题、日期、节目页、音频 URL、时长和逐字稿候选。
- `shownotes.raw.txt`：RSS 原始简介，仅作章节与身份核对证据。
- `transcript/segments.raw.json`：飞书妙记、通用 ASR 或公开逐字稿的原始结构化结果。
- `transcript/minutes.transcript.raw.txt`：使用妙记时保存的原始导出文本；不得覆盖。
- `transcript/transcript.meta.json`：取得通道、时间、来源 URL、妙记/音频链接、状态和质量字段。

推荐状态：

- `rss_transcript_found`
- `web_transcript_found`
- `minutes_audio_uploaded`
- `minutes_creation_submitted`
- `minutes_processing`
- `minutes_transcript_generated`
- `minutes_summary_updated`
- `minutes_failed_asr_fallback`
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
    └── YYYY-MM-DD_节目名_简短标题/
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

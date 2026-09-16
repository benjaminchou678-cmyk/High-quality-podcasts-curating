---
name: podcast-transcript-cleaner
description: 清洗、整理和规范播客或访谈逐字稿，在保留原始 ASR 证据的基础上生成带时间戳、多说话人区分、正文内阶段标题和质量风险标记的 Markdown/HTML 阅读版。用于 ASR 后轻编辑、说话人分段、风险标注与周报渲染；不用于摘要、事实纠错、观点改写或身份推断。
---

# 播客逐字稿清洗与整理

将原始分段转换为可读但可追溯的逐字稿。核心标准：**不折损、顺序不变、轻编辑、风险显式、允许带风险归档**。

## 输入

同一单集目录中读取：

- `metadata.json`：标题、节目、发布日期、节目页和音频时长。
- `transcript/segments.raw.json`：起止时间、speaker、文本和可选置信度；不得覆盖。
- `transcript/transcript.meta.json`：来源、ASR 时长与上游状态。
- `shownotes.raw.txt`：只提取明确章节时间点，不拼入正文。

缺少 `metadata.json` 或 `segments.raw.json` 时停止，不从简介重建逐字稿。

## 三层产物

1. **证据层**：原始分段和元信息，保持原样。
2. **阅读层**：`transcript.readable.md` 和周报 HTML。
3. **结构层**：`dialogue.readable.json`、`quality-report.json`。

## 工作流

1. 校验时间戳、空文本、时长覆盖、speaker 分布、长静默和置信度。
2. 将稳定声纹展示为 `说话人1`、`说话人2`、`说话人3`……；不推断身份。
3. 合并连续同说话人碎片：默认间隔不超过 3 秒，合并后不超过 420 字。
4. 仅规范空白、标点、完全相邻重复和对话块句末标点，不重写措辞。
5. 将可靠章节按时间插入正文；没有章节时每 15 分钟建立“自动分段”。
6. 生成阅读稿、结构化对话和质量报告。
7. 风险只标记，不阻止生成。

```bash
python3 <skill-dir>/scripts/clean_transcript.py <episode-dir>
```

## 编辑边界

允许：

- 统一空白和中英文标点形态。
- 合并同一说话人的连续短片段。
- 删除文本完全相同且时间重叠/紧邻的 ASR 重复。
- 补完整对话块的句末标点。

需要直接证据才能修正：

- 人名、公司名、产品名、缩写和专业术语。
- 金额、年份、比例、版本号等数字。
- 同音错字和 speaker 瞬时跳变。

禁止：

- 优化观点、事实纠错、补写内容、删除限定词。
- 将 Shownotes、简介或评论混入正文。
- 猜测说话人真实身份。

## 风险级别

- `normal`：未发现显著机器风险。
- `notice`：自动章节、少量低置信或少量长静默。
- `review_recommended`：覆盖不足、speaker 缺失、置信度不可用或长静默较多。
- `high_risk`：时间戳逆序、大段缺失、身份冲突或结构只能部分解析。

所有级别均允许生成，阅读稿头部必须显示机器转写声明、风险级别和原因。

详细阈值见 [`references/format-and-risk.md`](references/format-and-risk.md)。

## 阅读版结构

```markdown
# YYYY-MM-DD｜播客名｜单集标题

> ASR 机器转写，未经人工校对。
> 质量状态：...
> 说话人编号仅表示本文内不同声纹，不代表真实身份。

## 逐字稿

## 00:15:00｜阶段标题

**说话人2** · 00:15:04

发言正文。
```

不生成独立章节导航，不为每段发言使用标题。

## 周报 HTML

```bash
python3 <skill-dir>/scripts/render_html_reader.py <manifest.json> --output <report.html>
```

公开环境的逐字稿链接优先使用 `transcript_url`；企业环境可自行映射其他文档 URL 字段。链接必须是 HTTP/HTTPS，不接受本地绝对路径。

## 完成检查

- 原始证据未被改写。
- 阅读版时间顺序、首尾覆盖与输入一致。
- 结构层保留每块起止时间和 speaker。
- 风险已标记，而非阻止产物。
- 质量报告中的数字可复算。
- 输出不含凭据、内部路径或个人信息。

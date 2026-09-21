# 英文访谈中英对照规范

## 触发条件

仅在以下任一条件成立时启用双语阅读版：

- `metadata.json` 明确设置 `transcript_language: "en"`；
- `metadata.json` 设置 `bilingual: true` 且原文为英文；
- 用户明确要求英文访谈提供中英对照。

中文访谈、中文为主的混合访谈不自动翻译，也不为了统一格式补造英文原文。

## 数据结构

原始 `segments.raw.json` 的 `text` 永远保存英文证据，不覆盖。译文写入同一片段的可选字段：

```json
{
  "start_time": 12.0,
  "end_time": 18.5,
  "speaker": "speaker-a",
  "text": "The original English sentence.",
  "translation_zh": "对应的中文译文。"
}
```

也兼容 `text_zh` 作为输入字段，但规范化后统一输出 `translation_zh`。

## 阅读版格式

每个发言块严格采用：

```markdown
**说话人1** · 00:00:12

对应的中文译文。

> **英文原文**
> The original English sentence.
```

规则：

- 中文译文在上，英文原文在下；两者属于同一说话人和同一时间块。
- 英文原文使用引用块降低视觉权重，但必须完整保留，不折叠、不隐藏。
- 时间戳和说话人只显示一次，不在中英文之间重复。
- 译文不得增加原文没有的事实、因果、态度或确定性。
- 人名、公司名、产品名、论文名和专业缩写首次出现可写为 `中文名（English Name）`；后续可用稳定中文名或通行英文缩写。
- 数字、金额、年份、比例、版本号和否定/不确定表达必须与原文一致。
- 听不清、重叠发言等风险标记同时作用于译文与原文，不用译文掩盖原文缺陷。

## 议题提要与其他 bullet

- `议题提要` 的顶层与二级 bullet 默认全部使用中文。
- 文档内由本 Skill 新生成的摘要、风险原因、状态说明、章节说明和列表项默认使用中文。
- 必须保留的品牌名、产品名、组织名、论文名、代码标识或专业术语可保留英文，并在首次出现时给出中文解释。
- 不生成一套英文 bullet 与一套中文 bullet；只有完整逐字稿正文采用上下对照。

## 翻译覆盖与风险

质量报告增加：

- `translation_required`：是否要求中文译文。
- `translation_coverage_ratio`：含有效中文译文的英文非空片段数 / 英文非空片段数。
- `translation_missing_count`：缺少中文译文的英文片段数。

风险：

- 覆盖率为 100%：不新增翻译风险。
- `0 < coverage < 1`：标记 `translation_incomplete`，级别 `review_recommended`，仍输出英文原文；缺译段显示 `[中文译文待补]`。
- `coverage = 0`：标记 `translation_unavailable`，级别 `review_recommended`，不得伪造译文或用英文复制充当中文。

## 验证

- 每个英文发言块均保留原文。
- 有译文的块严格“中文在上、英文在下”。
- 译文块数、缺译块数和覆盖率可由 `dialogue.readable.json` 复算。
- 所有议题提要和普通 bullet 默认中文。
- 中文访谈不出现空的“英文原文”区块。

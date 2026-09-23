# 格式与风险规范

## 文件结构

```text
transcript/
├── segments.raw.json
├── transcript.meta.json
├── dialogue.readable.json
├── transcript.readable.md
└── quality-report.json
```

## 轻编辑

- 连续空白压缩为一个。
- 中文上下文中的半角 `, ; : ? !` 可转为全角。
- 对话块末尾已有 `。！？…?!.` 时保留，不在英文句号后追加中文句号。
- 只有完全相同文本在时间重叠或相邻不超过 0.5 秒时才能去重。
- 同 speaker、间隔不超过 3 秒、合并后不超过 420 字且不跨长静默时才合并。

## 正文内阶段标题

优先级：

1. Shownotes 中明确的 `HH:MM:SS / MM:SS + 标题`。
2. 用户提供章节。
3. 每 15 分钟自动分段。

章节直接插入正文，不生成独立导航，不将章节说明拼进对话。

## 指标

- `duration_coverage_ratio`：实际 ASR 时长 / 元信息时长。
- `low_confidence_ratio`：置信度低于 0.80 的片段比例。
- `very_low_confidence_ratio`：置信度低于 0.60 的片段比例。
- `missing_speaker_ratio`：归一后无 speaker 的非空片段比例。
- `speaker_mode_requested` / `speaker_mode_resolved`：请求模式与实际解析模式。
- `raw_speaker_count` / `normalized_speaker_count`：原始标签数量与归一后说话人数。
- `raw_missing_speaker_ratio`：归一前 speaker 缺失比例。
- `speaker_segment_counts` / `speaker_remap`：归一后各说话人片段数与原始标签映射。
- `timestamp_order_errors`：开始时间逆序次数。
- `long_gap_count`：相邻片段间隔超过 10 秒的次数。
- `empty_text_count`：空正文片段数。
- `deduplicated_exact_count`：删除的完全重复片段数。

没有置信度时相关指标为 `null`，并增加 `confidence_unavailable` 风险。

## 风险阈值

### normal

- 覆盖率 ≥ 0.95；
- 时间戳无逆序；
- speaker 完整；
- 低置信比例 < 0.05。

### notice

任一：自动章节；0.90 ≤ 覆盖率 < 0.95；0.05 ≤ 低置信比例 < 0.15；1–3 个长静默；多人模式发现稀有声纹聚类但不自动合并；单人模式将多个 ASR 声纹聚类统一为说话人1。

### review_recommended

任一：0.75 ≤ 覆盖率 < 0.90；0.15 ≤ 低置信比例 < 0.30；speaker 缺失、预期人数不一致或模式无法可靠确定；置信度不可用；长静默超过 3 个。

### high_risk

任一：覆盖率 < 0.75；时间戳逆序；低置信比例 ≥ 0.30；正文异常；单集身份冲突；结构只能部分解析。

风险等级取命中的最高档，所有等级均允许生成和归档。

## 阅读版

- 标题：`YYYY-MM-DD｜播客名｜单集标题`。
- 头部显示机器转写、风险级别和说话人声明。
- 阶段标题：`## HH:MM:SS｜标题`。
- 对话元信息：`**说话人N** · HH:MM:SS`。
- 不添加金句或事实纠错；仅在正文前生成基于全文、带时间证据的中文议题提要，不替代正文。

## 妙记 TXT 时间边界

仅有开始时间的导出标 `end_time_estimated: true`；`end_time_basis` 记录下一开始时间、媒体时长或未知。不得把推算的结束边界当作精确发言时间。该类输入不自动合并/去重，`duration_coverage_ratio`、`long_gap_count`、`long_gaps` 置为 `null`，风险包含 `end_times_estimated`。仍允许带风险生成及归档。

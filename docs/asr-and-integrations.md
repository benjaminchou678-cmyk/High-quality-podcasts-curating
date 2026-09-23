# 飞书妙记、ASR 与归档集成说明

## 默认转写策略

本项目按以下顺序取得全文：

1. RSS 显式逐字稿；
2. 公开节目页全文逐字稿；
3. 飞书妙记：没有公开全文时的默认音频转写通道；
4. 通用 ASR：妙记不可用或明确失败时的备选通道。

Skill 本身是工作流与规范，不附带语音模型、飞书账号、权限或额度。复制 Skill 不会自动复制原环境的妙记、云盘或 ASR 能力。

## 飞书妙记主通道

标准链路：

```text
公开音频 URL
  → 下载临时音频
  → 上传到原“按播客归档”文件夹
  → 使用 file_token 创建一次妙记
  → 等待逐字稿、说话人、时间戳与章节
  → 导出并转换为 segments.raw.json
  → 基于完整逐字稿生成中文议题提要
  → 写入妙记总结区
  → 原地创建/更新原豆包逐字稿与周报
```

妙记支持的原始音视频需满足平台限制：时长不超过 6 小时、大小不超过 6 GB，并使用其支持的音视频格式。上传成功不等于妙记已创建；妙记创建成功也不等于转写已就绪，必须按 `minute_token` 等待并回读。

妙记通常能提供时间戳、说话人分区、章节和原音频回听，但不保证片段置信度。缺少置信度时保持 `null` 并标记 `confidence_unavailable`，不得伪造数值。

### 顶部中文 bullet

妙记默认总结不保证符合本项目格式。逐字稿就绪后完整读取正文，生成 3–8 个中文顶层议题、每个 1–6 个二级要点，并保留时间证据；随后使用妙记总结更新能力替换顶部总结区。逐字稿正文始终保持节目原语言。

实际生成中，默认总结和章节可能晚于逐字稿就绪。若总结仍为空，继续查询同一 `minute_token`；不要重复创建妙记。按[妙记工作流](../skills/podcast-weekly-collector/references/feishu-minutes-workflow.md)的有限轮询预算执行。默认总结一直未就绪时保存待续状态；已取得的完整正文仍可继续生成豆包文档，不能据总结失败重做 ASR。

### 接回本项目证据层

使用：

```bash
python3 skills/podcast-weekly-collector/scripts/import_minutes_transcript.py \
  minutes/transcript.txt \
  <episode-dir> \
  --minute-url <minute_url> \
  --audio-file-url <audio_file_url>
```

生成：

- `transcript/minutes.transcript.raw.txt`
- `transcript/segments.raw.json`
- `transcript/transcript.meta.json`

`acquisition_method` 为 `feishu_minutes`。脚本拒绝覆盖任何已有证据；重导入使用独立运行目录。TXT 只有开始时间，结束时间标为推算值，不据此声称 100% 全文覆盖或无长静默。清洗报告会标 `end_times_estimated`，不可测指标为 `null`。

提要渲染入口为 `scripts/render_minutes_summary.py`（位于采集 Skill 下），输入同一 `topic-digest.json`；它只做校验和渲染，不承担翻译或改写。详细命令、有限轮询及恢复规则以 [妙记工作流](../skills/podcast-weekly-collector/references/feishu-minutes-workflow.md) 为准。

## 原共享文件夹保持不变

引入妙记不会改变原归档结构：

- 音频上传到原“按播客归档/节目名”文件夹；
- 豆包逐字稿仍在同一节目文件夹中创建或原地更新；
- 周报仍在原“按周归档/自然周”文件夹中创建或原地更新；
- 周报踪迹主链接仍指向豆包逐字稿，可在元信息附加妙记回听链接。

真实文件夹 URL/token 是私有运行时 `archive_context`，沿用原映射，不写入 GitHub。仅 Markdown 输出默认不创建妙记或文档，除非另外授权妙记转写。豆包文档可见不代表妙记权限相同；妙记回听链接仅在私有输出设置 `include_private_links: true` 后渲染。

这里只改转写来源，不自动移动妙记对象、改变目录或共享权限；原逐字稿与周报继续复用原文档 URL。

## 通用 ASR 备选

仅在下列情形启用：

- 环境没有飞书云盘或妙记能力；
- 用户没有权限或妙记额度；
- 文件超出妙记格式、时长或大小限制；
- 妙记创建或转写明确失败且不可恢复；
- 用户明确要求不用妙记。

可用实现包括 Agent 平台音频工具、云 ASR API、本地 Whisper / faster-whisper 等。不得同时让妙记和 ASR 转写同一单集。

最小输出：

```json
[
  {
    "start_time": 0.0,
    "end_time": 4.2,
    "text": "欢迎收听本期节目。"
  }
]
```

推荐同时返回 `speaker` 和 `confidence`。字段不存在时省略，不用假值填充。

## 降级规则

- 妙记转写明确失败且备用 ASR 已授权：记录阶段，再切换；用户拒绝授权不得绕过。总结写回失败但正文已取得时继续使用正文归档，不再转写。
- 无任何音频转写通道：仍可采集 RSS 并清洗公开逐字稿；其他单集标记为 `asr_required` 或 `unavailable`。
- 无 speaker：保留正文并标记 `speaker_missing`，不猜测身份。
- 无 confidence：指标写 `null` 并标记 `confidence_unavailable`。
- 无时间戳：不得伪造时间戳，也不能声称满足完整逐字稿标准。

## 临时文件清理

清理默认关闭。仅用户明确授权、确认文件是本任务下载的副本，且所选归档完成验证后，才删除该单个本地音频副本。失败时保留；永不自动删除 Drive 音频、妙记或转写证据。

## 能力测试清单

首次在新环境使用时，以短音频实测：

1. `lark-drive` 是否能上传文件到目标节目文件夹；
2. `lark-meeting` 是否能创建并读取妙记；
3. 妙记额度、格式、时长和大小限制；
4. 逐字稿是否完整、时间戳是否单调、说话人是否可区分；
5. 妙记总结是否可替换并回读；
6. 导入脚本能否稳定生成 `segments.raw.json`；
7. 原豆包文档与周报是否仍写入原文件夹；
8. 通用 ASR 备选是否能在妙记失败时独立工作。

## 安全建议

- 不把飞书文件夹 token、妙记 token、API key、cookie 或账号凭据写入 GitHub。
- 只处理合法公开音频，不绕过付费墙、登录或访问控制。
- 遵守播客来源条款、版权要求、企业数据政策及隐私规则。
- 日志中不要保留认证头或临时下载票据。

# ASR 接入契约

## 定义

ASR（Automatic Speech Recognition）通道是实际把音频转成文字的工具、模型或 API。Skill 只定义工作流与数据契约，不附带模型、账号、额度或云服务权限。

可用实现包括：

- Agent 平台自带音频转写工具；
- 云 ASR API；
- 本地 Whisper / faster-whisper；
- 能导出逐字稿的会议或妙记产品。

## 最小能力

至少返回：

```json
[
  {
    "start_time": 0.0,
    "end_time": 4.2,
    "text": "转写正文"
  }
]
```

推荐同时返回：

- `speaker`：说话人聚类编号；
- `confidence`：片段置信度，通常为 0–1。

没有可用字段时省略，不使用假值填充。

## 能力判定

普通 Agent 是否具备 ASR 取决于运行平台：

- 纯文本 Agent 通常没有；
- 能接收音频附件不代表能输出逐句时间戳；
- 能转写文本不代表支持 speaker diarization；
- 企业环境还取决于管理员安装的工具、登录、权限和额度。

必须用短音频实测以下项目：音频输入、完整正文、时间戳、置信度、说话人分区、长音频限制和结构化导出。

## 降级

- 无 ASR：仍可采集 RSS 并清洗来源自带的公开逐字稿；其他单集标记为 `asr_required` 或 `unavailable`。
- 无 speaker：保留正文并标记 `speaker_missing`，不猜测身份。
- 无 confidence：指标写 `null` 并标记 `confidence_unavailable`。
- 无时间戳：不得伪造时间戳，也不能声称满足本项目完整逐字稿标准。

## 安全

使用第三方 ASR 前确认音频允许发送给该服务。不得把 API key、cookie、认证头、临时下载票据或账号信息写入仓库、manifest 或日志。

# Tech PR Workbench

本地运行的 AI/科技采访日报与剪辑工作台。它会按日期区间发现 YouTube 和 B 站上的 AI 采访候选，展示摘要、原始链接、采访嘉宾识别结果，并在你点击“下载并翻译”后，把授权视频下载到本机、生成中文字幕、推荐高光片段，最后导出带字幕的剪辑序列视频。

> 默认定位：个人或小团队本地工具。请只下载你有权下载、编辑和再发布的素材。

## 功能

- AI 采访日报：按北京时间日期区间抓取候选视频。
- 来源：YouTube 优先，B 站补充；无 YouTube API key 时会降级到本机搜索。
- 人物识别：区分“追踪人物命中”和“识别出的采访嘉宾”。
- 一键处理：优先使用原中文字幕，其次英文字幕本地翻译，再其次本地转写。
- 剪辑工作台：播放器、中文字幕、时间轴高光建议、多段剪辑序列、导出 VTT/SRT/剪辑表/序列视频。
- 本地优先：SQLite、yt-dlp、FFmpeg、Argos Translate，可选 faster-whisper/Ollama/OpenAI。

## 是否涉及收费

默认配置不依赖额外付费 API：

- `yt-dlp`、FFmpeg、SQLite、Argos Translate、本地 Ollama 都是本机工具或开源软件，本项目不会向它们按量付费。
- YouTube Data API 用于发现公开视频元数据，主要受每日 quota 限制；默认配额可能不够大规模生产使用。
- OpenAI API 是可选项。只有当你在 `.env` 里设置 `CLOUD_AI_ENABLED=true` 并提供 `OPENAI_API_KEY` 时，才会调用云端付费模型。
- GitHub 公共仓库可免费托管代码；如果你启用额外的私有团队、Actions 大量 CI、Packages 等能力，可能会进入 GitHub 自身的计费范围。

## 平台支持

已在 macOS 本地开发和测试。Linux 通常可以直接运行。Windows 建议优先使用 WSL2；原生 Windows 也可以尝试，但需要确保 `uv`、Node.js、FFmpeg 都在 PATH 中。

依赖：

- Node.js 20+
- uv
- FFmpeg
- 可选：Ollama、opencli、faster-whisper

macOS 可用 Homebrew 安装基础依赖：

```bash
brew install node uv ffmpeg
```

## 快速启动

```bash
git clone https://github.com/judefluen-coder/tech-pr-workbench.git
cd tech-pr-workbench
npm run setup
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

`npm run setup` 会：

- 如果 `.env` 不存在，从 `.env.example` 复制一份。
- 安装后端依赖，包括本地翻译依赖。
- 安装前端依赖。

`npm run dev` 会同时启动：

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

## 配置

编辑 `.env`：

```env
YOUTUBE_API_KEY=
CLOUD_AI_ENABLED=false
OPENAI_API_KEY=
ARGOS_TRANSLATE_ENABLED=true
LOCAL_ASR_ENABLED=false
DOWNLOAD_ENGINE=yt-dlp
LOCAL_YTDLP_DISCOVERY=true
OPENCLI_DISCOVERY_ENABLED=true
BILIBILI_DISCOVERY_ENABLED=true
```

推荐第一步先不配置 OpenAI。需要更稳定的 YouTube 发现结果时，再配置 `YOUTUBE_API_KEY`。

## 下载与字幕策略

点击“下载并翻译”后，系统按顺序尝试：

1. 下载原视频和可用字幕。
2. 如果已有中文字幕，直接导入。
3. 如果只有英文字幕，用本地翻译生成中文字幕。
4. 如果没有字幕，并且启用了本地 ASR 或云端 AI，再做转写和翻译。

导出序列视频会把剪辑序列中的片段拼接成一个 MP4，并尽量烧录中文字幕。

## 测试

```bash
npm run test
```

或分别运行：

```bash
npm run test:backend
npm run build:frontend
```

## 合规提醒

- 日报发现阶段只保存元数据和原始链接。
- 自动下载用于本地剪辑工作流，请确保你有权下载、编辑和导出该视频。
- 不要提交 `.env`、`storage/` 里的数据库、下载视频、导出视频或字幕文件。

## 常见问题

### 没有 YouTube API key 能用吗？

能用，但发现覆盖率会下降。系统会尝试本机 opencli/yt-dlp 搜索和 B 站来源。

### 为什么有些视频显示“人物待确认”？

这表示标题、简介和已有字幕里没有明确采访嘉宾。下载翻译完成后，系统会用字幕再识别一次。

### 可以给非技术用户用吗？

可以作为本地工具使用。当前版本仍需要安装 Node.js、uv 和 FFmpeg；如果要完全给非技术同事使用，下一步建议做 macOS `.app` 或 Docker Desktop 一键包。

# Troubleshooting

## 项目无法启动

先运行：

```bash
npm run doctor
npm run setup
```

基础依赖是受支持版本的 Node.js、npm 和 uv。FFmpeg 缺失时网页仍能启动，但视频合并、抽音频和成片导出会受限。`npm run dev` 会同时启动前端、API 和 worker；停止这个命令会一起停止三者。

## OpenCLI 没有显示浏览器窗口

默认 `OPENCLI_WINDOW_MODE=background`，抓取窗口会在后台运行，避免抢走工作台焦点。这不表示 OpenCLI 没有执行。

需要观察或调试窗口时，在 `.env` 中临时设置：

```env
OPENCLI_WINDOW_MODE=foreground
OPENCLI_PREFLIGHT_ENABLED=true
```

然后重新运行 `npm run dev`。Docker 容器不能直接显示宿主机 OpenCLI 浏览器窗口；需要可视浏览器抓取时请使用原生启动模式。

## YouTube 没有结果或封面

- 配置 `YOUTUBE_API_KEY` 可以获得更稳定的元数据发现；API key 不能由项目自动创建。
- 没有 key 时，项目会尝试 OpenCLI 和 yt-dlp 回退，结果覆盖率会受登录状态、网络和平台限制影响。
- 先运行 `npm run doctor` 确认 OpenCLI 是否可用，再看页面顶部 YouTube 来源状态里的具体说明。
- 旧记录缺少封面时，可重新抓取对应日期；下载视频不是修复元数据封面的必要条件。

## 下载失败

- 确认素材允许下载和剪辑。
- 运行 `npm run doctor`，重点检查 FFmpeg。
- 在“处理任务”查看完整失败原因；修复依赖或网络后点击“重试”。
- YouTube 默认由 yt-dlp 处理，B站优先使用 OpenCLI 下载并有本地回退。XiaDown 是外部伴随工具，项目不会自动调用或安装它。
- 历史失败任务会保留作为记录；它们不代表当前环境仍然故障。

## 任务停住或重启后仍在处理中

下载、字幕和导出任务保存在 SQLite 中。正常重启 `npm run dev` 后，中断的 worker 任务会重新排队。页面“处理任务”会恢复任务进度，并提供失败重试。若 worker 没有启动，终端里不会出现 `[worker] ready`。

## 导出失败

- 确认 FFmpeg 可用、本地视频文件存在，并且剪辑序列至少有一个有效片段。
- 先看导出弹窗的预检项；阻塞项必须修复，风险项可以人工确认后继续。
- 自定义保存目录必须是本机可写路径。Docker 模式下使用容器映射的 `storage/Downloads` 或 `storage/Desktop`。
- 可运行 `SMOKE_VIDEO_ID=<本地视频编号> npm run smoke` 验证网页、API 和本地媒体读取。

## 刷新后状态没有恢复

日期、当前视频、工作视图、播放位置和剪辑草稿保存在当前浏览器的 localStorage。更换浏览器、无痕窗口或清理站点数据后不会共享这些状态；数据库中的任务、字幕、片段和导出记录不受影响。

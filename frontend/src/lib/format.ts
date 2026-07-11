export function formatDuration(seconds: number): string {
  const safe = Number.isFinite(seconds) ? seconds : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function formatDate(value: string): string {
  if (!value) return "待确认";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

export function formatTimecode(seconds: number): string {
  const safe = Math.max(seconds || 0, 0);
  const minutes = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "新增",
    shortlisted: "已入选",
    imported: "已导入",
    translated: "已翻译",
    clipped: "已打点",
    exported: "已导出",
    archived: "归档",
    discovered: "已发现",
    summarizing: "摘要中",
    ready: "可处理",
    downloading: "下载中",
    subtitle_fetching: "字幕中",
    transcribing: "转写中",
    translating: "翻译中",
    clip_ready: "可剪辑",
    queued: "排队中",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
  };
  return labels[status] ?? status;
}

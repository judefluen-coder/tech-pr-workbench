export interface ManualClipValidation {
  message: string;
  ok: boolean;
  severity: "ready" | "block";
}

export function buildManualClipValidation({
  duplicate,
  end,
  readyAction = "可以加入序列",
  start,
  timelineDuration,
}: {
  duplicate: boolean;
  end: number;
  readyAction?: string;
  start: number;
  timelineDuration: number;
}): ManualClipValidation {
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return { ok: false, severity: "block", message: "请输入有效的入点和出点秒数。" };
  }
  if (start < 0 || end < 0) {
    return { ok: false, severity: "block", message: "入点和出点不能小于 0。" };
  }
  if (end <= start) {
    return { ok: false, severity: "block", message: "出点必须晚于入点。" };
  }
  if (timelineDuration > 0 && end > timelineDuration + 0.1) {
    return { ok: false, severity: "block", message: `出点不能超过素材时长 ${formatTimecode(timelineDuration)}。` };
  }
  if (duplicate) {
    return { ok: false, severity: "block", message: "这个选区已经在剪辑序列里。" };
  }
  return { ok: true, severity: "ready", message: `片段时长 ${formatDuration(end - start)}，${readyAction}。` };
}

function formatDuration(seconds: number): string {
  const safe = Number.isFinite(seconds) ? seconds : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function formatTimecode(seconds: number): string {
  const safe = Math.max(seconds || 0, 0);
  const minutes = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

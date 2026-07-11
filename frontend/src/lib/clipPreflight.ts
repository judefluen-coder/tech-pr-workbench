export type ExportPreflightSeverity = "ready" | "warn" | "block";

export interface ExportPlanMark {
  end_seconds: number;
  start_seconds: number;
}

export interface ExportPreflightCheck {
  id: string;
  label: string;
  message: string;
  severity: ExportPreflightSeverity;
}

export interface ExportVersionPlan {
  duration: number;
  includedCount: number;
  shortfall: boolean;
  trimsLastClip: boolean;
}

export function buildExportVersionPlan(marks: ExportPlanMark[], targetDuration: number): ExportVersionPlan {
  const target = Number.isFinite(targetDuration) ? Math.max(targetDuration, 0) : 0;
  if (target <= 0) {
    return marks.reduce(
      (plan, mark) => {
        const duration = validMarkDuration(mark);
        if (duration <= 0) return plan;
        return { ...plan, duration: plan.duration + duration, includedCount: plan.includedCount + 1 };
      },
      { duration: 0, includedCount: 0, shortfall: false, trimsLastClip: false },
    );
  }

  let remaining = target;
  let duration = 0;
  let includedCount = 0;
  let trimsLastClip = false;
  for (const mark of marks) {
    const markDuration = validMarkDuration(mark);
    if (markDuration <= 0) continue;
    if (remaining <= 0.1) break;
    const plannedDuration = Math.min(markDuration, remaining);
    includedCount += 1;
    duration += plannedDuration;
    if (plannedDuration < markDuration - 0.05) trimsLastClip = true;
    remaining -= plannedDuration;
  }

  return {
    duration,
    includedCount,
    shortfall: duration < target - 0.05,
    trimsLastClip,
  };
}

export function buildExportVersionPreflightCheck({
  marks,
  sequenceDuration,
  targetDuration,
}: {
  marks: ExportPlanMark[];
  sequenceDuration: number;
  targetDuration: number;
}): ExportPreflightCheck {
  const plan = buildExportVersionPlan(marks, targetDuration);
  if (targetDuration <= 0) {
    return {
      id: "version",
      label: "导出版本",
      message: "会导出完整序列。",
      severity: "ready",
    };
  }
  if (plan.shortfall) {
    return {
      id: "version",
      label: "导出版本",
      message: `序列短于 ${formatPlanDuration(targetDuration)}，会导出全部 ${formatPlanDuration(sequenceDuration)}。`,
      severity: "warn",
    };
  }
  return {
    id: "version",
    label: "导出版本",
    message: `会导出 ${formatPlanDuration(targetDuration)} 版本，使用前 ${plan.includedCount} 段${plan.trimsLastClip ? "，并截短最后一段" : ""}。`,
    severity: "ready",
  };
}

function validMarkDuration(mark: ExportPlanMark): number {
  const start = Math.max(Number(mark.start_seconds) || 0, 0);
  const end = Math.max(Number(mark.end_seconds) || 0, start);
  return Math.max(end - start, 0);
}

function formatPlanDuration(seconds: number): string {
  const safe = Number.isFinite(seconds) ? Math.max(seconds, 0) : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

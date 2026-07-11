export type SequenceQualitySeverity = "ready" | "warn" | "block";

export interface ClipRange {
  end_seconds: number;
  id?: number;
  start_seconds: number;
}

export interface SequenceQualityIssue {
  id: string;
  label: string;
  markId?: number;
  message: string;
  severity: Exclude<SequenceQualitySeverity, "ready">;
}

export interface SequenceQualitySummary {
  issues: SequenceQualityIssue[];
  message: string;
  severity: SequenceQualitySeverity;
}

export interface SequenceMarkIssue {
  id: string;
  label: string;
  message: string;
  seekSeconds: number;
  severity: Exclude<SequenceQualitySeverity, "ready">;
}

export function buildSequenceQualitySummary(marks: ClipRange[]): SequenceQualitySummary {
  const invalidCount = marks.filter((mark) => mark.end_seconds <= mark.start_seconds).length;
  const shortCount = marks.filter((mark) => mark.end_seconds > mark.start_seconds && mark.end_seconds - mark.start_seconds < 3).length;
  const firstInvalidMark = marks.find((mark) => mark.end_seconds <= mark.start_seconds);
  const firstShortMark = marks.find((mark) => mark.end_seconds > mark.start_seconds && mark.end_seconds - mark.start_seconds < 3);
  const sortedValidMarks = marks
    .filter((mark) => mark.end_seconds > mark.start_seconds)
    .sort((left, right) => left.start_seconds - right.start_seconds || left.end_seconds - right.end_seconds);
  const overlapCount = sortedValidMarks.filter((mark, index) => index > 0 && mark.start_seconds < sortedValidMarks[index - 1].end_seconds).length;
  const firstOverlapMark = sortedValidMarks.find((mark, index) => index > 0 && mark.start_seconds < sortedValidMarks[index - 1].end_seconds);
  const issues: SequenceQualityIssue[] = [];

  if (invalidCount) {
    issues.push({
      id: "invalid-boundaries",
      label: "边界",
      markId: firstInvalidMark?.id,
      message: `${invalidCount} 段出点不晚于入点`,
      severity: "block",
    });
  }
  if (overlapCount) {
    issues.push({
      id: "overlap",
      label: "重叠",
      markId: firstOverlapMark?.id,
      message: `${overlapCount} 处时间重叠`,
      severity: "warn",
    });
  }
  if (shortCount) {
    issues.push({
      id: "short",
      label: "短片段",
      markId: firstShortMark?.id,
      message: `${shortCount} 段短于 3 秒`,
      severity: "warn",
    });
  }

  const severity = issues.some((issue) => issue.severity === "block") ? "block" : issues.length ? "warn" : "ready";
  return {
    issues,
    message: severity === "ready" ? "序列检查正常" : `${issues.length} 项需要复核`,
    severity,
  };
}

export function buildSequenceIssueMarkIds(marks: ClipRange[]): Set<number> {
  return new Set(buildSequenceIssueDetails(marks).keys());
}

export function buildSequenceIssueDetails(marks: ClipRange[]): Map<number, SequenceMarkIssue[]> {
  const details = new Map<number, SequenceMarkIssue[]>();
  const addIssue = (mark: ClipRange, issue: SequenceMarkIssue) => {
    if (mark.id === undefined) return;
    const current = details.get(mark.id) ?? [];
    details.set(mark.id, [...current, issue]);
  };

  for (const mark of marks) {
    if (mark.end_seconds <= mark.start_seconds) {
      addIssue(mark, {
        id: "invalid-boundaries",
        label: "边界",
        message: "出点不晚于入点",
        seekSeconds: mark.start_seconds,
        severity: "block",
      });
      continue;
    }
    if (mark.end_seconds - mark.start_seconds < 3) {
      addIssue(mark, {
        id: "short",
        label: "短片段",
        message: "短于 3 秒",
        seekSeconds: mark.start_seconds,
        severity: "warn",
      });
    }
  }

  const sortedValidMarks = marks
    .filter((mark) => mark.end_seconds > mark.start_seconds)
    .sort((left, right) => left.start_seconds - right.start_seconds || left.end_seconds - right.end_seconds);

  sortedValidMarks.forEach((mark, index) => {
    if (index === 0) return;
    const previous = sortedValidMarks[index - 1];
    if (mark.start_seconds >= previous.end_seconds) return;
    addIssue(previous, {
      id: `overlap-next-${mark.id ?? index}`,
      label: "重叠",
      message: "与下一段重叠",
      seekSeconds: previous.end_seconds,
      severity: "warn",
    });
    addIssue(mark, {
      id: `overlap-prev-${previous.id ?? index - 1}`,
      label: "重叠",
      message: "与上一段重叠",
      seekSeconds: mark.start_seconds,
      severity: "warn",
    });
  });

  return details;
}

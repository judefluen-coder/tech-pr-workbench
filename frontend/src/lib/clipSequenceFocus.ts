export function clipSequenceFocusSelectors(filter: string): string[] {
  if (filter === "copy") return [".marks-panel .mark-quality-flags .copy", ".marks-panel"];
  if (filter === "issues") return [".marks-panel .mark-quality-flags .block", ".marks-panel .mark-quality-flags .warn", ".marks-panel"];
  return [".marks-panel"];
}

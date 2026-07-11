export function buildTranscriptWindow<T extends { index: number }>(rows: T[], requestedLimit: number, activeIndex: number, buffer = 20): T[] {
  const safeLimit = Math.max(1, Math.floor(requestedLimit));
  const activePosition = activeIndex >= 0 ? rows.findIndex((item) => item.index === activeIndex) : -1;
  const end = Math.max(safeLimit, activePosition >= 0 ? activePosition + Math.max(1, buffer) : 0);
  return rows.slice(0, end);
}

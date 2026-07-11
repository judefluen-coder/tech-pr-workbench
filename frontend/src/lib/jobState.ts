import type { Job } from "../types";

export function isActiveJobStatus(status: string): boolean {
  return status === "queued" || status === "running";
}

export function jobVideoId(job: Pick<Job, "payload">): number | null {
  try {
    const payload = JSON.parse(job.payload || "{}");
    const videoId = Number(payload?.video_id);
    return Number.isInteger(videoId) && videoId > 0 ? videoId : null;
  } catch {
    return null;
  }
}

export function jobResult<T>(job: Pick<Job, "result">): T | null {
  try {
    const result = JSON.parse(job.result || "{}");
    return result && typeof result === "object" && !Array.isArray(result) ? (result as T) : null;
  } catch {
    return null;
  }
}

export function buildJobState(records: Job[]) {
  const jobs: Record<number, Job> = {};
  const activeJobIdsByVideo: Record<number, number> = {};
  const latestJobIdsByVideo: Record<number, number> = {};

  [...records]
    .sort((left, right) => right.id - left.id)
    .forEach((job) => {
      jobs[job.id] = job;
      const videoId = jobVideoId(job);
      if (!videoId) return;
      if (!latestJobIdsByVideo[videoId]) latestJobIdsByVideo[videoId] = job.id;
      if (!activeJobIdsByVideo[videoId] && isActiveJobStatus(job.status)) activeJobIdsByVideo[videoId] = job.id;
    });

  return { jobs, activeJobIdsByVideo, latestJobIdsByVideo };
}

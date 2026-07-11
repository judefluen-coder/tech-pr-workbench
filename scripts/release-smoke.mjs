import assert from "node:assert/strict";

const frontendBase = (process.env.SMOKE_FRONTEND_URL || "http://127.0.0.1:5173").replace(/\/$/, "");
const apiBase = (process.env.SMOKE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const requestedVideoId = Number(process.env.SMOKE_VIDEO_ID || 0);

async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(10_000), ...options });
  } catch (error) {
    throw new Error(`无法连接 ${url}：${error instanceof Error ? error.message : String(error)}`);
  }
  assert.ok(response.ok, `${url} 返回 HTTP ${response.status}`);
  return response;
}

async function json(path) {
  return (await request(`${apiBase}${path}`)).json();
}

const frontend = await (await request(frontendBase)).text();
assert.match(frontend, /id=["']root["']/, "前端 HTML 缺少 React 根节点");

const health = await json("/api/health");
assert.equal(health.ok, true, "API 健康检查未通过");

const daily = await json("/api/daily");
assert.ok(Array.isArray(daily.items), "日报响应缺少 items 数组");
assert.ok(Array.isArray(daily.source_runs), "日报响应缺少 source_runs 数组");

const jobs = await json("/api/jobs?limit=5");
assert.ok(Array.isArray(jobs), "任务接口没有返回数组");

if (Number.isInteger(requestedVideoId) && requestedVideoId > 0) {
  const clip = await json(`/api/items/${requestedVideoId}/clip`);
  assert.equal(clip.video?.id, requestedVideoId, "剪辑接口返回了错误的视频");
  assert.ok(Array.isArray(clip.transcripts), "剪辑接口缺少字幕数组");
  assert.ok(Array.isArray(clip.clip_marks), "剪辑接口缺少片段数组");
  if (clip.media_url) {
    await request(`${apiBase}${clip.media_url}`, { headers: { Range: "bytes=0-0" } });
  }
  console.log(`OK  video #${requestedVideoId} - ${clip.transcripts.length} subtitles, ${clip.clip_marks.length} clips`);
}

console.log(`OK  frontend - ${frontendBase}`);
console.log(`OK  api - ${apiBase}`);
console.log(`OK  daily - ${daily.items.length} items, ${daily.source_runs.length} sources`);
console.log(`OK  jobs - ${jobs.length} recent records`);

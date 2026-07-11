import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "frontend/src/lib/clipDelivery.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
const { buildClipDeliveryBrief, buildClipDeliveryHandoffPrompt, buildClipDeliveryNextStep, buildClipDeliverySummary, clipDeliveryCopyGaps } = await import(moduleUrl);

const video = {
  channel_title: "Tech Channel",
  platform: "youtube",
  published_at: "",
  title: "AI Founder Interview",
  url: "https://example.com/watch",
};

test("clip delivery copy gaps describe missing handoff fields", () => {
  assert.deepEqual(clipDeliveryCopyGaps({ label: "未命名片段", note: "", quote: "" }), ["标题", "备注", "引用"]);
  assert.deepEqual(clipDeliveryCopyGaps({ label: "产品观点", note: "有备注", quote: "" }), ["引用"]);
  assert.deepEqual(clipDeliveryCopyGaps({ label: "产品观点", note: "有备注", quote: "原文" }), []);
});

test("clip delivery brief reports pending review, copy, and export work", () => {
  const brief = buildClipDeliveryBrief({
    assets: [],
    marks: [
      {
        end_seconds: 12,
        label: "已确认观点",
        note: "可发社媒",
        quote: "这段可以做开场。",
        start_seconds: 0,
        status: "approved",
      },
      {
        end_seconds: 28,
        label: "未命名片段",
        note: "",
        quote: "",
        start_seconds: 12,
        status: "ready",
      },
    ],
    origin: "http://localhost:5173",
    renderResult: null,
    video,
  });

  assert.match(brief, /交付状态：待处理 · 1 段待确认 · 1 段缺文案 · 待导出成片/);
  assert.match(brief, /2\. 未命名片段（00:12 - 00:28，0:16，可用，缺文案：标题、备注、引用）/);
  assert.match(brief, /成片 MP4：待导出/);
});

test("clip delivery summary exposes scan-friendly handoff status", () => {
  assert.deepEqual(
    buildClipDeliverySummary({
      assets: [],
      marks: [
        {
          end_seconds: 12,
          label: "已确认观点",
          note: "可发社媒",
          quote: "这段可以做开场。",
          start_seconds: 0,
          status: "approved",
        },
        {
          end_seconds: 28,
          label: "未命名片段",
          note: "",
          quote: "",
          start_seconds: 12,
          status: "ready",
        },
      ],
      origin: "http://localhost:5173",
      renderResult: null,
    }),
    {
      approvedCount: 1,
      exportedUrls: [],
      isReady: false,
      marksCount: 2,
      missingCopyCount: 1,
      pendingItems: ["1 段待确认", "1 段缺文案", "待导出成片"],
      sequenceDuration: 28,
      statusLabel: "待处理 · 1 段待确认 · 1 段缺文案 · 待导出成片",
      unapprovedCount: 1,
    },
  );
});

test("clip delivery brief reports a ready exported handoff and dedupes asset urls", () => {
  const brief = buildClipDeliveryBrief({
    assets: [{ kind: "exported_sequence", url: "/exports/sequence.mp4" }],
    marks: [
      {
        end_seconds: 10,
        label: "产品观点",
        note: "社媒标题方向",
        quote: "AI 正在进入业务流程。",
        start_seconds: 0,
        status: "approved",
      },
    ],
    origin: "http://localhost:5173",
    renderResult: {
      clip_status_filter: "approved",
      clips: [{ id: 1 }],
      rendered_duration_seconds: 10,
      sequence_url: "/exports/sequence.mp4",
    },
    video,
  });

  assert.match(brief, /交付状态：可交付/);
  assert.match(brief, /最近导出：仅已确认 · 1 段 · 实际 0:10/);
  assert.match(brief, /成片 MP4：http:\/\/localhost:5173\/exports\/sequence\.mp4/);
  assert.equal((brief.match(/http:\/\/localhost:5173\/exports\/sequence\.mp4/g) ?? []).length, 1);
});

test("clip delivery summary marks fully reviewed exported sequences as ready", () => {
  assert.deepEqual(
    buildClipDeliverySummary({
      assets: [{ kind: "exported_sequence", url: "/exports/sequence.mp4" }],
      marks: [
        {
          end_seconds: 10,
          label: "产品观点",
          note: "社媒标题方向",
          quote: "AI 正在进入业务流程。",
          start_seconds: 0,
          status: "approved",
        },
      ],
      origin: "http://localhost:5173",
      renderResult: {
        clip_status_filter: "approved",
        clips: [{ id: 1 }],
        rendered_duration_seconds: 10,
        sequence_url: "/exports/sequence.mp4",
      },
    }),
    {
      approvedCount: 1,
      exportedUrls: ["http://localhost:5173/exports/sequence.mp4"],
      isReady: true,
      marksCount: 1,
      missingCopyCount: 0,
      pendingItems: [],
      sequenceDuration: 10,
      statusLabel: "可交付",
      unapprovedCount: 0,
    },
  );
});

test("clip delivery next step prioritizes copy, review, export, then handoff copy", () => {
  const pendingCopySummary = {
    approvedCount: 1,
    exportedUrls: [],
    isReady: false,
    marksCount: 2,
    missingCopyCount: 1,
    pendingItems: ["1 段缺文案", "待导出成片"],
    sequenceDuration: 28,
    statusLabel: "待处理 · 1 段缺文案 · 待导出成片",
    unapprovedCount: 0,
  };
  assert.deepEqual(buildClipDeliveryNextStep(pendingCopySummary, { canAutofillCopy: true }), { id: "copy", label: "补齐文案" });
  assert.deepEqual(buildClipDeliveryNextStep(pendingCopySummary, { canAutofillCopy: false }), { id: "view-copy", label: "查看缺文案" });

  assert.deepEqual(
    buildClipDeliveryNextStep({
      ...pendingCopySummary,
      missingCopyCount: 0,
      pendingItems: ["1 段待确认", "待导出成片"],
      statusLabel: "待处理 · 1 段待确认 · 待导出成片",
      unapprovedCount: 1,
    }),
    { id: "review", label: "继续审片" },
  );
  assert.deepEqual(
    buildClipDeliveryNextStep({
      ...pendingCopySummary,
      missingCopyCount: 0,
      pendingItems: ["待导出成片"],
      statusLabel: "待处理 · 待导出成片",
      unapprovedCount: 0,
    }),
    { id: "export", label: "导出成片" },
  );
  assert.deepEqual(
    buildClipDeliveryNextStep({
      ...pendingCopySummary,
      exportedUrls: ["http://localhost:5173/exports/sequence.mp4"],
      isReady: true,
      missingCopyCount: 0,
      pendingItems: [],
      statusLabel: "可交付",
      unapprovedCount: 0,
    }),
    { id: "copy-brief", label: "复制交付稿" },
  );
});

test("clip delivery handoff prompt distinguishes ready and pending exports", () => {
  assert.deepEqual(
    buildClipDeliveryHandoffPrompt({
      approvedCount: 1,
      exportedUrls: ["http://localhost:5173/exports/sequence.mp4"],
      isReady: true,
      marksCount: 1,
      missingCopyCount: 0,
      pendingItems: [],
      sequenceDuration: 10,
      statusLabel: "可交付",
      unapprovedCount: 0,
    }),
    {
      label: "复制交付稿",
      message: "1 段已确认，成片已导出。",
      tone: "ready",
    },
  );
  assert.deepEqual(
    buildClipDeliveryHandoffPrompt({
      approvedCount: 1,
      exportedUrls: ["http://localhost:5173/exports/sequence.mp4"],
      isReady: false,
      marksCount: 2,
      missingCopyCount: 1,
      pendingItems: ["1 段待确认", "1 段缺文案"],
      sequenceDuration: 28,
      statusLabel: "待处理 · 1 段待确认 · 1 段缺文案",
      unapprovedCount: 1,
    }),
    {
      label: "复制状态稿",
      message: "1 段待确认 · 1 段缺文案",
      tone: "pending",
    },
  );
});

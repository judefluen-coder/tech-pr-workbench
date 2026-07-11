export type ClipEditShortcut = "approve" | "cancel" | "mark-in" | "mark-out" | "next" | "preview" | "previous" | "save";

export interface ClipEditShortcutInput {
  altKey?: boolean;
  ctrlKey?: boolean;
  ignorePlainKeys?: boolean;
  key: string;
  metaKey?: boolean;
  shiftKey?: boolean;
}

export function resolveClipEditShortcut(input: ClipEditShortcutInput): ClipEditShortcut | null {
  const key = input.key.toLowerCase();
  const commandKey = Boolean(input.metaKey || input.ctrlKey);

  if (commandKey && input.shiftKey && !input.altKey && key === "enter") return "approve";
  if (commandKey && !input.shiftKey && !input.altKey && key === "enter") return "save";
  if (!commandKey && input.altKey && !input.shiftKey && key === "arrowup") return "previous";
  if (!commandKey && input.altKey && !input.shiftKey && key === "arrowdown") return "next";
  if (commandKey || input.altKey) return null;
  if (key === "escape") return "cancel";
  if (input.ignorePlainKeys) return null;
  if (key === "i") return "mark-in";
  if (key === "o") return "mark-out";
  if (key === "p" || key === " ") return "preview";
  return null;
}

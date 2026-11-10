import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";

type CaptureMsg = {
  type: "capture";
  kind: "text" | "image";
  text?: string;
  dataUrl?: string;
  timestamp: string;
  id: string;
};

/** Imperative API type, derived from the component props so we don't depend on
 * internal type-subpath exports of the package. */
type ExcalidrawAPI = Parameters<
  NonNullable<React.ComponentProps<typeof Excalidraw>["excalidrawAPI"]>
>[0];

/* ------------------------------------------------------------------ */
/* Grid placement                                                      */
/* ------------------------------------------------------------------ */

const GRID = {
  originX: 100,
  originY: 100,
  cellW: 360,
  cellH: 280,
  cols: 4,
};

/**
 * Assign a slot for an item of size w x h. Returns the item's top-left
 * position (centered inside the slots it spans) and how much to advance
 * the placement counter so nothing ever overlaps.
 */
function placeItem(
  n: number,
  w: number,
  h: number
): { x: number; y: number; next: number } {
  const colSpan = Math.min(
    GRID.cols,
    Math.max(1, Math.ceil(w / GRID.cellW))
  );
  const rowSpan = Math.max(1, Math.ceil(h / GRID.cellH));

  let col = n % GRID.cols;
  let slot = n;

  // A wide item must not run off the right edge of the grid row —
  // move it to the start of the next row instead.
  if (col + colSpan > GRID.cols) {
    slot += GRID.cols - col;
    col = 0;
  }

  const spanW = colSpan * GRID.cellW;
  const spanH = rowSpan * GRID.cellH;
  const x = GRID.originX + col * GRID.cellW + Math.max(0, (spanW - w) / 2);
  const y =
    GRID.originY +
    Math.floor(slot / GRID.cols) * GRID.cellH +
    Math.max(0, (spanH - h) / 2);

  // Advance: wide items consume their columns, tall items consume whole
  // rows below them (conservative — guarantees no overlap).
  const next = slot + colSpan + (rowSpan - 1) * GRID.cols;
  return { x, y, next };
}

/** Derive the next placement slot from restored elements. Prefers the exact
 * slot info we stash in `customData`; falls back to counting capture groups. */
function deriveCounter(elements: readonly any[]): number {
  let max = 0;
  for (const el of elements) {
    const cd = el?.customData;
    if (cd && typeof cd.slot === "number") {
      max = Math.max(max, cd.slot + (typeof cd.span === "number" ? cd.span : 1));
    }
  }
  if (max > 0) return max;
  const groups = new Set<string>();
  for (const el of elements) {
    for (const g of el?.groupIds ?? []) {
      if (typeof g === "string" && g.startsWith("capture-")) groups.add(g);
    }
  }
  return groups.size;
}

/* ------------------------------------------------------------------ */
/* Text layout helpers                                                 */
/* ------------------------------------------------------------------ */

const TEXT_FONT = { fontSize: 16, fontFamily: 2 } as const; // 2 = normal (non-hand-drawn)
const LABEL_FONT = { fontSize: 10, fontFamily: 2 } as const;
const LABEL_COLOR = "#8a8f98";
const MAX_ITEM_WIDTH = 320;
const LINE_HEIGHT = 1.25;

function computeTextLayout(text: string, fontSize: number, fontFamily: number, maxWidth: number) {
  const font = { fontSize, fontFamily };
  const lib = ExcalidrawLibAny;
  let wrapped = text;
  let width = maxWidth;
  let height: number | null = null;
  try {
    if (typeof lib.wrapText === "function") {
      wrapped = lib.wrapText(text, font, maxWidth);
    }
    if (typeof lib.measureText === "function") {
      const m = lib.measureText(wrapped, font);
      if (m && typeof m.height === "number") {
        height = m.height;
        if (typeof m.width === "number" && m.width > 0) width = m.width;
      }
    }
  } catch {
    /* fall back to approximation below */
  }
  if (height == null) {
    const lines = wrapped.split("\n").length;
    height = lines * fontSize * LINE_HEIGHT;
  }
  return { text: wrapped, width, height };
}

/** Approximate greedy wrap used only if the package's wrapText is unavailable. */
function fallbackWrap(text: string, fontSize: number, maxWidth: number): string {
  const charW = fontSize * 0.55;
  const perLine = Math.max(8, Math.floor(maxWidth / charW));
  const out: string[] = [];
  for (const para of text.split("\n")) {
    let line = "";
    for (const word of para.split(/\s+/)) {
      if ((line + " " + word).trim().length > perLine && line) {
        out.push(line.trim());
        line = word;
      } else {
        line = (line + " " + word).trim();
      }
    }
    out.push(line);
  }
  return out.join("\n");
}

/* ------------------------------------------------------------------ */
/* Element construction                                                */
/* ------------------------------------------------------------------ */

function baseProps(
  id: string,
  x: number,
  y: number,
  width: number,
  height: number,
  groupIds: string[]
) {
  return {
    id,
    x,
    y,
    width,
    height,
    angle: 0,
    strokeColor: "#1e1e1e",
    backgroundColor: "transparent",
    fillStyle: "solid" as const,
    strokeWidth: 1,
    strokeStyle: "solid" as const,
    roughness: 1,
    opacity: 0, // animated to 100 by the highlight ease-in
    groupIds,
    frameId: null,
    roundness: null,
    seed: Math.floor(Math.random() * 2 ** 31),
    version: 1,
    versionNonce: Math.floor(Math.random() * 2 ** 31),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
  };
}

function makeTextElement(
  id: string,
  x: number,
  y: number,
  text: string,
  fontSize: number,
  fontFamily: number,
  color: string,
  groupIds: string[]
) {
  const layout = computeTextLayout(text, fontSize, fontFamily, MAX_ITEM_WIDTH);
  return {
    ...baseProps(id, x, y, layout.width, layout.height, groupIds),
    type: "text" as const,
    strokeColor: color,
    text: layout.text,
    fontSize,
    fontFamily,
    textAlign: "left" as const,
    verticalAlign: "top" as const,
    containerId: null,
    originalText: layout.text,
    lineHeight: LINE_HEIGHT,
    baseline: layout.height,
  };
}

function loadImageSize(dataUrl: string): Promise<{ w: number; h: number }> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () =>
      resolve({
        w: img.naturalWidth || 300,
        h: img.naturalHeight || 200,
      });
    img.onerror = () => resolve({ w: 300, h: 200 });
    img.src = dataUrl;
  });
}

/* NOTE: `wrapText`/`measureText` are NOT exported from the package root in
 * v0.18.1 (checked the .d.ts), despite appearing in older docs. We access
 * them defensively through an `any` view of the namespace and fall back to a
 * local greedy-wrap + line-count approximation when missing. */
import * as ExcalidrawNamespace from "@excalidraw/excalidraw";
const ExcalidrawLibAny = ExcalidrawNamespace as any as Record<string, any>;

/* ------------------------------------------------------------------ */
/* Room sync helpers (only active with ?room=<id> in the URL)          */
/* ------------------------------------------------------------------ */

const ROOM_ID_RE = /^[a-z0-9-]{3,64}$/;

/** Read + sanitize the ?room= query param. Returns null in solo mode. */
function getRoomId(): string | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("room");
    if (!raw) return null;
    const id = raw.trim().toLowerCase();
    return ROOM_ID_RE.test(id) ? id : null;
  } catch {
    return null;
  }
}

/** Random client id for the room hello handshake. */
function newClientId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/* ------------------------------------------------------------------ */
/* App                                                                 */
/* ------------------------------------------------------------------ */

export default function App() {
  const apiRef = useRef<ExcalidrawAPI | null>(null);
  const elementsRef = useRef<readonly any[]>([]);
  const appStateRef = useRef<any>(null);
  const filesRef = useRef<Record<string, any>>({});

  const counterRef = useRef(0);
  const saveTimerRef = useRef<number | null>(null);
  const restoredRef = useRef(false);
  const pendingSceneRef = useRef<{ elements: any[]; appState: any; files: Record<string, any> } | null>(null);

  const [connected, setConnected] = useState(false);

  /* ---------------------------- auto-save --------------------------- */

  const doSave = useCallback(async () => {
    try {
      await fetch("/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          elements: elementsRef.current,
          appState: {
            viewBackgroundColor:
              appStateRef.current?.viewBackgroundColor ?? "#ffffff",
          },
          files: filesRef.current,
        }),
      });
    } catch {
      /* saving must never block or break the UI */
    }
  }, []);

  const scheduleSave = useCallback(() => {
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      void doSave();
    }, 800);
  }, [doSave]);

  /* --------------------- highlight ease-in (<=400ms) ---------------- */

  const animsRef = useRef<Map<string, number>>(new Map());
  const animRafRef = useRef<number>(0);

  const runHighlightAnim = useCallback(() => {
    const api = apiRef.current;
    if (!api) {
      animRafRef.current = 0;
      return;
    }
    const now = performance.now();
    const anims = animsRef.current;
    let changed = false;
    const elements = elementsRef.current.map((el: any) => {
      const start = anims.get(el.id);
      if (start === undefined) return el;
      const t = Math.min(1, (now - start) / 300);
      const eased = t * t * (3 - 2 * t); // smoothstep — no bounce
      const opacity = Math.round(100 * eased);
      if (t >= 1) anims.delete(el.id);
      if (opacity !== el.opacity) {
        changed = true;
        return { ...el, opacity };
      }
      return el;
    });
    if (changed) {
      api.updateScene({ elements });
      elementsRef.current = elements;
    }
    if (anims.size > 0) {
      animRafRef.current = requestAnimationFrame(runHighlightAnim);
    } else {
      animRafRef.current = 0;
    }
  }, []);

  const startHighlight = useCallback(
    (ids: string[]) => {
      const now = performance.now();
      for (const id of ids) animsRef.current.set(id, now);
      if (animRafRef.current === 0) {
        animRafRef.current = requestAnimationFrame(runHighlightAnim);
      }
    },
    [runHighlightAnim]
  );

  /* --------------------------- insert capture ------------------------ */

  const insertCapture = useCallback(
    async (msg: CaptureMsg) => {
      const api = apiRef.current;
      if (!api || !msg?.id) return;

      // Dedupe repeated captures with the same id.
      const itemElId = `${msg.id}-item`;
      if (filesRef.current[msg.id] || elementsRef.current.some((e: any) => e.id === itemElId)) {
        return;
      }

      const groupId = `capture-${msg.id}`;
      const groupIds = [groupId];
      const labelId = `${msg.id}-ts`;

      let itemEl: any;
      let fileId: string | null = null;

      if (msg.kind === "image" && msg.dataUrl) {
        const { w, h } = await loadImageSize(msg.dataUrl);
        const scale = Math.min(1, 320 / Math.max(w, h));
        const iw = Math.max(1, Math.round(w * scale));
        const ih = Math.max(1, Math.round(h * scale));
        const slot = placeItem(counterRef.current, iw, ih);

        fileId = msg.id;
        api.addFiles([
          {
            id: fileId as any,
            dataURL: msg.dataUrl as any,
            mimeType: "image/png",
          },
        ] as any);

        itemEl = {
          ...baseProps(itemElId, slot.x, slot.y, iw, ih, groupIds),
          type: "image" as const,
          fileId,
          status: "saved" as const,
          scale: [1, 1],
          customData: { slot: counterRef.current, span: slot.next - counterRef.current },
        };
        counterRef.current = slot.next;

        const label = makeTextElement(
          labelId,
          slot.x, // below-left of the item
          slot.y + ih + 8,
          msg.timestamp,
          10,
          2,
          LABEL_COLOR,
          groupIds
        );
        api.updateScene({
          elements: [...elementsRef.current, itemEl, label],
        });
        startHighlight([itemElId, labelId]);
      } else if (msg.kind === "text" && typeof msg.text === "string" && msg.text.trim()) {
        const layout = computeTextLayout(msg.text, 16, TEXT_FONT.fontFamily, MAX_ITEM_WIDTH);
        const slot = placeItem(counterRef.current, layout.width, layout.height);
        itemEl = {
          ...makeTextElement(
            itemElId,
            slot.x,
            slot.y,
            msg.text,
            16,
            TEXT_FONT.fontFamily,
            "#1e1e1e",
            groupIds
          ),
          customData: { slot: counterRef.current, span: slot.next - counterRef.current },
        };
        counterRef.current = slot.next;

        const label = makeTextElement(
          labelId,
          slot.x,
          slot.y + layout.height + 8,
          msg.timestamp,
          10,
          2,
          LABEL_COLOR,
          groupIds
        );
        api.updateScene({
          elements: [...elementsRef.current, itemEl, label],
        });
        startHighlight([itemElId, labelId]);
      }
    },
    [startHighlight]
  );

  /* ------------------------------ restore ---------------------------- */

  const tryRestore = useCallback(() => {
    if (restoredRef.current) return;
    const api = apiRef.current;
    const scene = pendingSceneRef.current;
    if (!api || !scene) return;
    restoredRef.current = true;

    counterRef.current = deriveCounter(scene.elements);
    try {
      const fileValues = Object.values(scene.files ?? {});
      if (fileValues.length > 0) {
        api.addFiles(
          fileValues.map((f: any) => ({
            id: f.id as any,
            dataURL: f.dataURL as any,
            mimeType: f.mimeType ?? "image/png",
            created: f.created ?? Date.now(),
          })) as any
        );
      }
      api.updateScene({
        elements: scene.elements,
        appState: scene.appState?.viewBackgroundColor
          ? { viewBackgroundColor: scene.appState.viewBackgroundColor }
          : undefined,
      });
    } catch {
      /* a corrupt scene must never break the app */
    }
  }, []);

  /* --------------------------- mount effects ------------------------- */

  useEffect(() => {
    let cancelled = false;

    // 1. Load existing scene (same origin, relative path).
    (async () => {
      try {
        const res = await fetch("/scene");
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled || !data || typeof data !== "object") return;
        const elements = Array.isArray(data.elements) ? data.elements : [];
        pendingSceneRef.current = {
          elements,
          appState: data.appState ?? {},
          files: data.files ?? {},
        };
        tryRestore();
      } catch {
        /* no scene yet — start empty */
      }
    })();

    // 2. WebSocket with 2s auto-reconnect.
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      try {
        ws = new WebSocket(
          `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`
        );
      } catch {
        reconnectTimer = window.setTimeout(connect, 2000);
        return;
      }
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) reconnectTimer = window.setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data));
          if (msg?.type === "capture") void insertCapture(msg as CaptureMsg);
        } catch {
          /* ignore malformed frames */
        }
      };
    };
    connect();

    return () => {
      cancelled = true;
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      if (saveTimerRef.current !== null) window.clearTimeout(saveTimerRef.current);
    };
  }, [insertCapture, tryRestore]);

  /* ------------------------- room sync state ------------------------ */
  /* Only active with ?room=<id> in the URL (see getRoomId). In solo mode
   * none of this runs and behavior is unchanged. A SECOND WebSocket (next
   * to the /ws capture hub above) relays scene changes through /room/<id>. */

  const roomId = useMemo(() => getRoomId(), []);
  const [roomConnected, setRoomConnected] = useState(false);
  const [peerCount, setPeerCount] = useState(0);
  const [copied, setCopied] = useState(false);
  // Room bar visibility — remembered, so hiding it once keeps it hidden.
  // Default true the first time so new users discover Copy Link.
  const [roomBarOpen, setRoomBarOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem("gwb-roombar") !== "hidden";
    } catch {
      return true;
    }
  });

  const [hotkey, setHotkey] = useState("...");
  useEffect(() => {
    fetch("/config").then(r => r.json()).then(j => setHotkey(j.display));
  }, []);

  const updateHotkey = async (newHotkey: string) => {
    const r = await fetch("/config", {
      method: "POST",
      body: JSON.stringify({ hotkey: newHotkey.toLowerCase() }),
      headers: { "Content-Type": "application/json" },
    });
    if (r.ok) {
      const j = await r.json();
      setHotkey(j.display);
    } else {
      alert("Invalid hotkey format. Try e.g. ctrl+shift+c");
    }
  };

  const toggleRoomBar = useCallback((open: boolean) => {
    setRoomBarOpen(open);
    try {
      localStorage.setItem("gwb-roombar", open ? "open" : "hidden");
    } catch {
      /* ignore */
    }
  }, []);

  /* ------------------------ update notification ---------------------- */
  /* The server compares the installed copy against GitHub every few hours.
   * When one is available we show a small calm pill — installing stays a
   * manual double-click on the UPDATE file (never mid-use, never silent). */
  const [updateAvailable, setUpdateAvailable] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const r = await fetch("/update-status");
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled && j && j.update_available) setUpdateAvailable(true);
      } catch {
        /* offline — nothing to nag about */
      }
    };
    check();
    const t = window.setInterval(check, 60 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  const roomWsRef = useRef<WebSocket | null>(null);
  const myIdRef = useRef<string>("");
  const lastPeerCountRef = useRef(0);
  // Echo suppression: version of each element as last applied FROM the room.
  const lastRemoteRef = useRef<Map<string, number>>(new Map());
  // Last state we broadcast per element id (diff baseline).
  const lastSentRef = useRef<Map<string, { version: number; isDeleted: boolean }>>(new Map());
  const sentFilesRef = useRef<Set<string>>(new Set());
  const roomTimerRef = useRef<number | null>(null);
  const snapshotTimerRef = useRef<number | null>(null);

  const roomSend = useCallback((msg: any) => {
    const ws = roomWsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(msg));
      } catch {
        /* sync must never block or break the UI */
      }
    }
  }, []);

  /* Full scene once, on room open and when someone joins (peers count up). */
  const sendSnapshot = useCallback(() => {
    const files: Record<string, string> = {};
    for (const [fid, f] of Object.entries(filesRef.current) as [string, any][]) {
      if (f?.dataURL) {
        files[fid] = f.dataURL;
        sentFilesRef.current.add(fid);
      }
    }
    roomSend({ kind: "snapshot", elements: elementsRef.current, files });
  }, [roomSend]);

  const scheduleSnapshot = useCallback(() => {
    if (snapshotTimerRef.current !== null) window.clearTimeout(snapshotTimerRef.current);
    snapshotTimerRef.current = window.setTimeout(() => {
      snapshotTimerRef.current = null;
      sendSnapshot();
    }, 300); // let coalescing peers settle so bursts don't produce N snapshots
  }, [sendSnapshot]);

  /* Merge a remote payload (kind "elements" | "snapshot") into the scene. */
  const applyRemote = useCallback((payload: any) => {
    const api = apiRef.current;
    if (!api || !payload || typeof payload !== "object") return;
    try {
      const merged = elementsRef.current.slice();
      const idxOf = new Map<string, number>();
      merged.forEach((el: any, i: number) => {
        if (el && typeof el.id === "string") idxOf.set(el.id, i);
      });
      const incoming = Array.isArray(payload.elements) ? payload.elements : [];
      let changed = false;
      for (const e of incoming) {
        if (!e || typeof e !== "object" || typeof e.id !== "string") continue;
        const ev = e.version ?? 0;
        const idx = idxOf.get(e.id);
        if (idx === undefined) {
          merged.push(e);
          idxOf.set(e.id, merged.length - 1);
        } else {
          const cur = merged[idx];
          const cv = cur?.version ?? 0;
          // Newer version wins; ties break to the younger `updated`.
          const take = ev > cv || (ev === cv && (e.updated ?? 0) >= (cur?.updated ?? 0));
          if (!take) continue;
          merged[idx] = e;
        }
        lastRemoteRef.current.set(e.id, ev); // remember exactly what we applied
        lastSentRef.current.set(e.id, { version: ev, isDeleted: !!e.isDeleted });
        changed = true;
      }
      if (!changed) return;
      // Missing files (addFiles dedupes; we pre-filter anyway).
      const files = payload.files;
      if (files && typeof files === "object") {
        const recs: any[] = [];
        for (const [fid, v] of Object.entries(files) as [string, any][]) {
          if (filesRef.current[fid]) continue;
          const dataURL = typeof v === "string" ? v : v?.dataURL;
          if (dataURL) recs.push({ id: fid, dataURL, mimeType: "image/png" });
        }
        if (recs.length) api.addFiles(recs as any);
      }
      // Pass the live appState straight back so the view is never reset.
      api.updateScene({
        elements: merged,
        appState: appStateRef.current ? { ...appStateRef.current } : undefined,
      });
    } catch {
      /* a bad remote payload must never break the app */
    }
  }, []);

  /* Diff the current scene against the last-sent map and broadcast it. */
  const broadcastDiff = useCallback(() => {
    const elements = elementsRef.current;
    const changed: any[] = [];
    const fileIds = new Set<string>();
    for (const el of elements as any[]) {
      if (!el || typeof el.id !== "string") continue;
      // Echo suppression: skip exactly what we last applied from the room.
      const remoteV = lastRemoteRef.current.get(el.id);
      if (remoteV !== undefined && (el.version ?? 0) === remoteV) continue;
      const sent = lastSentRef.current.get(el.id);
      if (!sent || sent.version !== (el.version ?? 0) || sent.isDeleted !== !!el.isDeleted) {
        changed.push(el);
        if (typeof el.fileId === "string") fileIds.add(el.fileId);
      }
    }
    if (changed.length === 0) return;
    // Files the peers have never seen go out first.
    const newFiles: Record<string, string> = {};
    for (const fid of fileIds) {
      if (sentFilesRef.current.has(fid)) continue;
      const f = (filesRef.current as Record<string, any>)[fid];
      if (f?.dataURL) {
        newFiles[fid] = f.dataURL;
        sentFilesRef.current.add(fid);
      }
    }
    if (Object.keys(newFiles).length > 0) roomSend({ kind: "files", files: newFiles });
    for (const el of changed) {
      lastSentRef.current.set(el.id, { version: el.version ?? 0, isDeleted: !!el.isDeleted });
    }
    roomSend({ kind: "elements", elements: changed });
  }, [roomSend]);

  const scheduleRoomBroadcast = useCallback(() => {
    if (roomTimerRef.current !== null) window.clearTimeout(roomTimerRef.current);
    roomTimerRef.current = window.setTimeout(() => {
      roomTimerRef.current = null;
      broadcastDiff();
    }, 250);
  }, [broadcastDiff]);

  const copyLink = useCallback(() => {
    const link = window.location.href;
    (async () => {
      try {
        await navigator.clipboard.writeText(link);
        setCopied(true);
      } catch {
        try {
          window.prompt("Copy this link:", link); // iOS Safari fallback
        } catch {
          /* ignore */
        }
      }
    })();
    window.setTimeout(() => setCopied(false), 1500);
  }, []);

  /* Room WebSocket — second socket, 2s auto-reconnect, same as /ws above. */
  useEffect(() => {
    if (!roomId) return;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let disposed = false;
    myIdRef.current = newClientId();

    const connect = () => {
      if (disposed) return;
      try {
        // Room lives on the same server as the page, unless ?relay=<host>
        // overrides it — that's how a local board joins a room on the
        // deployed cloud copy (see DEPLOY.md).
        const relayParam = new URLSearchParams(location.search).get("relay");
        const base = relayParam
          ? relayParam.replace(/^http:/, "ws:").replace(/^https:/, "wss:")
          : `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
        ws = new WebSocket(`${base}/room/${roomId}`);
      } catch {
        reconnectTimer = window.setTimeout(connect, 2000);
        return;
      }
      roomWsRef.current = ws;
      ws.onopen = () => {
        setRoomConnected(true);
        try {
          ws?.send(JSON.stringify({ type: "hello", id: myIdRef.current }));
        } catch {
          /* ignore */
        }
        scheduleSnapshot();
      };
      ws.onclose = () => {
        setRoomConnected(false);
        if (!disposed) reconnectTimer = window.setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data));
          if (msg?.type === "peers" && typeof msg.count === "number") {
            const prev = lastPeerCountRef.current;
            lastPeerCountRef.current = msg.count;
            setPeerCount(msg.count);
            if (msg.count > prev) scheduleSnapshot(); // someone joined
          } else if (msg?.type === "change" && msg.payload) {
            applyRemote(msg.payload);
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };
    connect();

    return () => {
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (snapshotTimerRef.current !== null) window.clearTimeout(snapshotTimerRef.current);
      if (roomTimerRef.current !== null) window.clearTimeout(roomTimerRef.current);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      roomWsRef.current = null;
      lastPeerCountRef.current = 0;
      setRoomConnected(false);
    };
  }, [roomId, applyRemote, scheduleSnapshot]);

  /* ------------------------------- render ---------------------------- */

  return (
    <div style={{ width: "100vw", height: "100vh" }}>
      <Excalidraw
        theme="light"
        excalidrawAPI={(api) => {
          apiRef.current = api;
          tryRestore();
        }}
        onChange={(elements, appState, files) => {
          elementsRef.current = elements;
          appStateRef.current = appState;
          filesRef.current = files;
          scheduleSave();
          if (roomId) scheduleRoomBroadcast(); // room mode only; solo unchanged
        }}
      />
      {roomId && roomBarOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9998,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            padding: "6px 12px",
            background: "rgba(255,255,255,0.85)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            borderBottom: "1px solid rgba(0,0,0,0.08)",
            fontSize: 13,
            color: "#555",
          }}
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            🔗 Shared room: <strong style={{ color: "#1e1e1e" }}>{roomId}</strong>
            <span
              title={roomConnected ? "Room connected" : "Connecting…"}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: roomConnected ? "#3fb950" : "#e5534b",
                display: "inline-block",
                transition: "background 0.3s ease",
              }}
            />
            · {peerCount} online
          </span>
          <button
            onClick={copyLink}
            style={{
              padding: "8px 16px",
              fontSize: 14,
              fontWeight: 600,
              color: "#fff",
              background: "#1e1e1e",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            {copied ? "Copied!" : "Copy Link"}
          </button>
          <button
            onClick={() => {
              const newHk = prompt("Enter new shortcut (e.g. ctrl+shift+c or cmd+shift+c):", hotkey.toLowerCase());
              if (newHk) updateHotkey(newHk);
            }}
            title="Click to change your shortcut"
            style={{
              padding: "8px 12px",
              fontSize: 13,
              fontWeight: 500,
              color: "#333",
              background: "#f0f0f0",
              border: "1px solid rgba(0,0,0,0.12)",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            ⌨️ {hotkey}
          </button>
          <button
            onClick={() => toggleRoomBar(false)}
            title="Hide the room bar (bring it back with the small pill at the top-left)"
            aria-label="Hide room bar"
            style={{
              padding: "4px 10px",
              fontSize: 13,
              color: "#777",
              background: "transparent",
              border: "1px solid rgba(0,0,0,0.12)",
              borderRadius: 6,
              cursor: "pointer",
              lineHeight: 1.4,
            }}
          >
            –
          </button>
        </div>
      )}
      {updateAvailable && (
        <a
          href="https://github.com/GauthamWho/G-WhiteBoard#starting-it-every-day-10-seconds"
          target="_blank"
          rel="noreferrer"
          title="A new version is on GitHub. Open the G-WhiteBoard folder and double-click the UPDATE file."
          style={{
            position: "fixed",
            bottom: 14,
            right: 14,
            zIndex: 9998,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 12px",
            fontSize: 12,
            color: "#3d2e00",
            background: "#ffe9a8",
            border: "1px solid #e3c341",
            borderRadius: 999,
            textDecoration: "none",
            boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
          }}
        >
          ⬆ Update available
        </a>
      )}
      {roomId && !roomBarOpen && (
        <button
          onClick={() => toggleRoomBar(true)}
          title="Show the room bar"
          aria-label="Show room bar"
          style={{
            position: "fixed",
            top: 0,
            left: 10,
            zIndex: 9998,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "3px 10px",
            fontSize: 11,
            color: "#666",
            background: "rgba(255,255,255,0.75)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            border: "1px solid rgba(0,0,0,0.08)",
            borderTop: "none",
            borderRadius: "0 0 8px 8px",
            cursor: "pointer",
          }}
        >
          🔗 {peerCount}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: roomConnected ? "#3fb950" : "#e5534b",
              display: "inline-block",
            }}
          />
        </button>
      )}
      <div
        title={connected ? "Connected" : "Disconnected"}
        style={{
          position: "fixed",
          left: 10,
          bottom: 10,
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: connected ? "#3fb950" : "#e5534b",
          opacity: 0.85,
          zIndex: 9999,
          pointerEvents: "auto",
          cursor: "default",
          transition: "background 0.3s ease",
        }}
      />
    </div>
  );
}

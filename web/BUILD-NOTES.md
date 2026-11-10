# Whiteboard Catcher — Web Frontend

Vite + React 18 + TypeScript + `@excalidraw/excalidraw` 0.18.1.
Builds to `web/dist/` (served by the Python clipboard-catcher server at `GET /`).

## How it works

### Scene restore (on load)
- `GET /scene` (relative, same origin). If the response has `elements`, we call
  `excalidrawAPI.addFiles(Object.values(files))` and `updateScene({ elements, appState })`.
  Excalidraw's internal `restore()` fills any missing element props on the way in.

### WS capture insert (`ws://<same-host>/ws`, auto-reconnect every 2 s)
- **Image**: natural size is read via a hidden `Image()` decode, scaled so the
  long side is ≤ 320 px (aspect kept, no upscaling). The binary file record is
  registered with `excalidrawAPI.addFiles([{ id, dataURL, mimeType: "image/png" }])`
  (the capture id *is* the fileId), then an `image` element with that `fileId`
  is added.
- **Text**: fontSize 16, wrapped to max width 320 px, and width/height are
  computed up front (see "wrapText quirk" below).
- **Timestamp label**: a separate small text element (fontSize 10,
  `#8a8f98`) placed at `item.x, item.y + item.height + 8` (below-left).
- **Grouping**: item + label share `groupIds: ["capture-<captureId>"]`, so
  selecting/dragging one moves both. Element ids are `<captureId>-item` and
  `<captureId>-ts`.
- **Dedupe**: a capture id that already exists (as fileId or element id) is ignored,
  so server replays / double sends don't duplicate items.

### Auto-grid placement (no overlap, ever)
- Grid: origin (100, 100), cell 360×280, 4 columns. `col = n % 4`,
  `row = floor(n / 4)`; the item is centered inside the cell(s) it spans.
- Oversized items span multiple slots: wide items are snapped to the start of
  the next row if they'd run off the right edge, and the counter advances by
  `colSpan + (rowSpan - 1) * 4` (tall items consume whole rows below them —
  conservative, which is what guarantees zero overlap).
- **Persistence of the counter**: each item element carries
  `customData: { slot, span }` (survives the save/restore round-trip because
  `customData` is part of the element schema and we POST the raw elements).
  On restore the counter is `max(slot + span)`; if that's absent (old saves),
  it falls back to counting distinct `capture-*` groupIds.

### Auto-save
- `onChange(elements, appState, files)` keeps refs of the latest scene and
  debounces 800 ms, then `POST /save` with
  `{ elements, appState: { viewBackgroundColor }, files }`. Fire-and-forget;
  failures are swallowed and never block the UI. Note `onChange` also delivers
  the binary `files` map — that's the only place files are read from (matches
  the required `{ id, dataURL, mimeType, created }` shape).

### Landing highlight
- New elements are inserted at `opacity: 0` and eased to `opacity: 100` over
  ~300 ms (smoothstep via rAF, no bounce). The animation patches the latest
  scene (from the onChange ref), so it doesn't clobber user edits in flight.

### Connection dot
- 8 px dot, bottom-left corner, green/red, tooltip on hover only. No banners.

## Excalidraw API quirks hit
1. **`wrapText` / `measureText` are NOT exported from the package root in
   0.18.1** (verified against `dist/types/excalidraw/index.d.ts` and the prod
   bundle), despite appearing in the task brief / older docs. The app tries
   them defensively (via an `any` view of the namespace) and falls back to a
   local greedy word-wrap + `lines × fontSize × 1.25` height estimate.
2. `addFiles` uses branded types (`FileId`, `DataURL`) — plain strings need
   `as any` casts in TS.
3. Since 0.18 the stylesheet must be imported explicitly:
   `import "@excalidraw/excalidraw/index.css"` (resolves through package
   `exports` to `dist/prod/index.css`).
4. Manually built partial elements are fine: `updateScene` runs them through
   `restore()`, which fills defaults.

## Untested / caveats
- **Live WebSocket + real captures are untested** — the Python server (port
  8765) wasn't up during development; only `npm run build` was verified
  (exit 0, `dist/index.html` + JS bundles present). Message handling follows
  the specified JSON shape exactly.
- `POST /save` and `GET /scene` against the real server are likewise untested;
  relative paths assume same-origin serving from `web/dist`.
- Text measurement falls back to an approximation until/unless the package
  exports the measurement helpers in a future version; a few px of label
  drift vs. Excalidraw's own metrics is possible in the fallback path.

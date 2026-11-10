# V3 warehouse magnifier

The warehouse viewer now has a **Лупа** button. It opens a 224 px lens beside the cursor and enlarges that point in the live rendered view. Playback continues and the overview camera stays unchanged.

- Default 3×; wheel or `+` / `−` selects 1.5×–6×.
- Click the button again or press `Escape` to turn it off.
- The button supports keyboard activation; arrow keys move the inspected point.
- Leaving the warehouse canvas hides the lens. It stays within the browser window at the edges.
- The complete composed A/B frame is sampled, including both side-by-side and swipe views.
- Paused pointer movement uses the cached frame and adds no 3D draws or continuous idle animation loop.

The shared V3 scene owns initialization and cleanup. This covers Twin, Warehouse V3, common N0–N4 scenarios, Heavy Inbound and NativePair. The final change is V3-only: no V2 source modifications or V2 cases in the accepted matrix. No mobile work was added.

`checks.json` indexes exact source hashes, served build bytes and browser evidence. The production build and TypeScript check pass. All **10 V3 browser groups** pass on Intel UHD / Chrome D3D11, with no unexpected Page, console, HTTP or request errors. Browser-owned processes are confirmed closed.

The tests observe real `drawImage` source rectangles and WebGL calls rather than relying only on the helper's counters. They cover actual mouse activation, keyboard controls, live playback, wheel camera/clock invariance, zoom bounds, both A/B modes, pause/idle behavior, edges/resize/leave, actual context loss/reload, all shared V3 consumers and repeated disposal. Corner dispatch events are explicitly labelled synthetic; ordinary mouse/wheel/keyboard input uses Playwright. NativePair uses synthetic hash-checked no-op bundles, not a new backend capture.

The lens enlarges existing rendered pixels; it does not modify models, geometry, inventory or operational admission. Independent bounded source review found no concrete P1/P2 issue in the V3 capture, input and cleanup paths.

To repeat from `frontend`, use a production build and preview:

```powershell
npm run build
npm run preview -- --host 127.0.0.1 --port 4282 --strictPort
```

In a second terminal, from `frontend`:

```powershell
$env:QOIMA_TEST_BASE_URL='http://127.0.0.1:4282'
npm run test:warehouse:magnifier -- --out ../work/warehouse-magnifier-browser/NEW_RUN
```

Use a new output directory. `QOIMA_TEST_DIST_ROOT` optionally selects an isolated production build. These checks require installed Chrome and hardware WebGL; mobile and other GPU/platform behavior are outside this run.

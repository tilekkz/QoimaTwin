# Visual performance — frozen night build

Measured from the production viewer on 2026-11-06 at 22:27–22:29 UTC. Full raw
samples and browser/GPU identity are in [PERFORMANCE.json](PERFORMANCE.json).
This is the large visual fixture, not a backend load or throughput benchmark.

Chrome156 headless, Windows, Intel UHD Graphics through ANGLE/D3D11, 12 logical
CPU threads, 16GB reported browser memory; one1366×768 viewport, DPR1, low
quality, sound muted, fixture10×. No Blender renderer ran during measurement.
The500s fixture resets once within each window. Initial loading and a1.5s
warmup are excluded; all subsequent frame intervals are included.

| Camera | Actual window | Median FPS | Mean FPS | p95 frame | Max calls | Max triangles |
|---|---:|---:|---:|---:|---:|---:|
| Full overview | 60.001s | 142.86 | 100.83 | 14ms | 154 | 270,248 |
| Follow P01 / near geometry | 60.003s | 140.85 | 99.38 | 14ms | 191 | 418,632 |

The measured low mode exceeds the30FPS target in both windows. The close
camera exceeds the soft350k-triangle/180-call budgets by68,632 triangles and
eleven calls at its peak; this is recorded rather than hidden by reducing the
warehouse or removing near geometry. The21 loaded modular models total
3,235,060bytes; calibration and the separate static master are not loaded in
the main viewer. A different browser, laptop power state, high shadows or a
future densely active backend run needs its own measurement.

Reproduce after `npm ci` and `npm run build`, with the local production viewer
running:

```powershell
$env:QOIMA_TEST_URL='http://127.0.0.1:4180'
node tools/measure-visual-performance.mjs
```

Run from `frontend/`. The script writes the JSON and two actual screenshots.
`requestAnimationFrame` sampling measures delivered presentation intervals;
it does not claim GPU-only timings or a guaranteed frame rate.

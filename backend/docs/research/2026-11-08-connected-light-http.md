# Connected SMALL CLI and live HTTP evidence

The backend publication/API candidate after `00cabfa` was exercised on November 8,
2026, with the frozen `explicit-source-small-three-units-v1` profile. This is a
bounded connected SMALL run, not full V3 acceptance or physical hand-contact proof.

An actual loopback Uvicorn server accepted the public profile request, executed
the real process worker, and served its resulting manifest, raw files, captured
checkpoints and event windows. This check used network requests rather than an
injected TestClient processor. The owned server exited with code 0.

| Observation | Result |
| --- | --- |
| Native run ID | `3d160cd54bbd3ff68a092fac2df345444514593089e2b9b6f22c47e1779a5cd7` |
| Public API run ID | `fc78912a5d2234c5566b50934eab20abedb7200eb0b07c2fe1d708372d5d23da` |
| Frozen input SHA256 | `b1c62e61f80afe0e1e31fd0590f245080ad06423ffcff4898f8ee27189ae2ce6` |
| Files checked | 17, totaling 46,127,485 raw bytes |
| CLI/API identity | Every returned file was byte-identical to the separate CLI execution |
| Integrity | Every file length, SHA256 and HTTP ETag matched its inventory entry |
| Repeated POST | Identical response; exactly one actual worker attempt |
| Captured reads | Reading ticks 0, 60s, 30s, 60s and H preserved the repeated 60s state |
| Uncaptured tick | Tick 1 returned 422 |
| Arbitrary seek | No endpoint; request returned 404 |
| Event windows | `[0, 60s)` accepted; exceeding 60s by one microsecond returned 422 |

Stock checks used source facts and independent arithmetic: 12,256 initial units,
three shipped units, and 12,253 remaining units. Shipped mass was
`3 * 0.035 + 0.05 = 0.155 kg`, including the explicitly declared parcel material.
The native event count and elapsed simulation time are observations, not expected
test values derived from engine output.

The measured first POST took 498.0515817 seconds and the cached POST took
0.3859513 seconds on this shared development machine. Those timings include
execution/publication/verification work and concurrent development load. They
are lifecycle measurements, not a throughput benchmark or a performance target.
The 46 MB export is also an observed size, not a client-memory guarantee.

Local evidence is retained at `D:/QoimaTwin-runs/v3-light-api-20261108/report.json`,
`lifecycle.json` and `server.log`; the standalone check is
`D:/QoimaTwin-wt/v3-light-api-smoke.py`. The independent CLI artifact is at
`D:/QoimaTwin-runs/v3-light-cli-20261108`. Evidence directories are outside Git.

All responses retain `operational_admission=false`; full V3, frontend adaptation,
hand-contact proof, arbitrary seek and interpolation remain false. Receipt
creation, all cargo classes/ports and N0-N4 comparisons require later integrated
verification. See [API usage](../v3-light-api.md) and
[publication semantics](../adr/0049-connected-flow-publication.md).

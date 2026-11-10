# Current V3 desktop recording helper

Status: authored and syntax checked; not recorded or exported yet. Root executes
this only after the complete current QA run and final source/build freeze.
It does not reuse or promote the older November 9 demonstration video.

```powershell
node frontend/tools/record-final-desktop-v3.mjs --out work/v3/final-desktop-recording-NEW
```

The output folder must be new and inside repository `work/`. The helper uses
the built preview at `http://127.0.0.1:4224`, hardware Chrome with D3D11,
`--mute-audio --no-proxy-server`, a 1600 × 1000 viewport and DPR 1. It uses
the installed `ffmpeg` and `ffprobe` from PATH. Optional `--ffmpeg PATH` and
`--ffprobe PATH` select existing local executables; nothing is installed or
downloaded.

The helper prewarms two actual Scenario Page recordings, N3 and N4, before
the story. This allows the export to cut between ready viewer states without
showing warehouse loading screens. Both original WebM recordings are retained.
`readyOffset`, per-page opening/ready times, actual chapter wall times and
three contiguous source-video intervals are recorded in the receipt.

| Chapter | Target wall time | Actual viewer content |
| --- | ---: | --- |
| Warehouse overview | 7 s | N3 top and perspective views of the rectangular warehouse |
| Original STANDARD carry | 9 s | Original body and whole carton in the native loaded-walk phase, 1× |
| SMALL source | 10 s | Same single clamp, source approach/grip/extraction, 1× |
| SMALL at PK02 | 7 s | Whole carton and same tool on the actual native support |
| Source LONG pickup | 7 s | Original source HU on F02, 1× |
| Source LONG mounting | 7 s | Native attachment work, 1× |
| Source gate | 9 s | Visible 30× UI playback followed by the whole HU retained outside |
| N4 | 10 s | The same 24 source worker IDs, actual role movement and pending work |
| Final N3 and A/B | 18 s | Six completed native ports, counts and same-clock no-op A/B |

Target story length is 84 seconds; the actual export must measure 60–90
seconds. The UI timeline deliberately seeks between chapters. Playback speed
changes use the real visible Page control; the encoded footage is not sped up.
There are no added DOM overlays, generated images, slides, interpolated frames
or soundtrack. No Twin structural-B layout is inserted into this recording.

Final N3 assertions retain the explicit 2700-second horizon, the 20 original
requests plus one declared WEST pallet, 24 workers, two vehicles and 530 source
HUs. Final visible/upstream/downstream counts are 531/10/2, with six completed
visual flows. Source LONG remains on F02 outside the gate; recipient unloading
and order dispatch remain false. The A/B segment requires the same input hash
and clock, a tie and no declared winner.

The recording path is Playwright `recordVideo`. Contexts are flushed and raw
WebMs saved before closing the remote browser transport. If the public remote
save fails, only a unique existing native WebM inside that recording's owned
local directory may be retained as a fallback. Missing or ambiguous raw video
fails the export. FFprobe verifies that each raw recording retains the required
wall-time interval before FFmpeg trims and concatenates it.

The final MP4, raw WebMs, chapter posters, decoded MP4 review frames,
`story.json`, `export.json` and `capture-metadata.json` stay in the owned output
folder. Source hashes and served-current-dist hashes accompany the receipt.
PID/CIM creation-time attestation limits cleanup to the owned Chrome process
tree and any identified recorder encoder children. Chrome absence is checked
after cleanup. Root must review the decoded chapter posters and actual export
before treating H04 as complete.

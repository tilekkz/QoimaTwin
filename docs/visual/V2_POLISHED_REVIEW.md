# V2 polished — preserved alternative for independent review

This branch preserves the72×48m V2 industrial-miniature version after the visual revision. A separate V3 branch develops the144×72m boxy-cartoon alternative. The user requested both versions remain available for a friend to test and choose between.

V2 revisions: connected personnel proportions, cart/tote fit, clearer folded cartons and packaging, improved forklift silhouette, shorter physical4.65m racks with3unchanged logical levels, coherent conveyor surfaces/clock-driven stripes, detailed near models, precise close-view bounds, neutral light and adaptive shadows. Original864addresses/24people/6packing stations retained.

Validation already completed on the committed source candidate: production build/typecheck,33/33core+browser checks,33/33GLBvalidation with0errors/warnings,23/23binary geometry checks,84fresh browser model views inspected. Detailed provenance is in `VISUAL_REVISION_BROWSER.md`, `VISUAL_REVISION_STORAGE.md`, `VISUAL_REVISION_EQUIPMENT.md`, `BROWSER_QA.json` and `GLB_VALIDATION.json`.

Current polished High performance results are in `PERFORMANCE_HIGH.json`. The new Low series was interrupted at the V3 transition; existing `PERFORMANCE.json` and night demo video refer to the older night delivery and must not be presented as new-polish measurements/video. This version remains a labelled synthetic visual fixture; it does not claim a live warehouse/AI/DES run.

Source launch from `frontend`: `npm ci`, then `npm run dev -- --host 127.0.0.1`. Production: `npm run build`, then `npm run preview -- --host 127.0.0.1`. Open the printed local URL. V2 remains the default entry on this branch. Final dual-version packages will include their own tested launch instructions and exact commits.

For the friend: test overview/zoom/model stands, pick and cart/tote contacts, belt pause/block/turns, packing and forklift loading, seek/reset/follow, mute/reduced motion, browser errors and FPS on the same machine/settings. Record issues and preferred version after also testing V3; it has3×the scene area and separately reported measurements. No external message is sent automatically.

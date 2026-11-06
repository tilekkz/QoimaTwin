# Replay boundary (participant A)

Implementation begins after environment preparation. Consume the canonical Run
from `src/contracts`; use absolute simulation seconds and half-open action
intervals. Reconstruct state on seek/reset. Never calculate new routes, handling
times or final KPI in the viewer. Implement against hand_checked_run.json before
connecting participant B's API. See the root 03_3D_Scene_and_Replay.md.

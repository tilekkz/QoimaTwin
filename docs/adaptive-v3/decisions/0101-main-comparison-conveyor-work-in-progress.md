# ADR 0101 — Initial conveyor work in progress in the main comparison

## Status

Proposed for the frontend comparison branch.

## Context

The main comparison has a finite 240-second visual episode. Two carriers with
starts at 0 and 64 seconds left variant B empty after 223.17 seconds. Their
source-sized geometry projects to approximately two pixels in the full
warehouse overview. The source conveyor supplies its geometry, payload
envelope, 0.55 m/s speed and 0.8-second transfer dwell.

## Decision

Use six finite visual carriers with starts at −128, −64, 0, 64, 128 and
192 seconds. Negative starts declare the initial work already on the conveyor.
The episode retains its boundary at 240 seconds. Each tote contains the native
0.32 × 0.24 × 0.24 m SMALL_CARTON at scale 1 above its 0.012 m base. Packing
changes the representation from the loaded tote to the parcel. Existing
42-second A and 12-second B packing cues retain their authored visual basis.

Below 16 screen pixels per metre, show a small box symbol at the cargo's
projected position. Above that threshold the native models carry the display.
Each comparison pass clips its own symbols. The clock waits until motion
installation completes, including delayed loading and retained paused links.

## Consequences and validation

The six starts are an explicit presentation choice. Source geometry and timing
remain authoritative for their respective inputs. The representation keeps
`source_kind=visual_fixture`, `engine_operation=false` and
`operational_admission=false`. Inventory and paid comparison use their existing
source inputs.

CPU checks cover both variants over 0–240 seconds, every route edge and phase
boundary, source speed, payload dimensions, separation, query isolation,
reverse seek and the final hold. Browser acceptance covers the normal overview,
close-up, swipe clipping and narrow-screen controls.

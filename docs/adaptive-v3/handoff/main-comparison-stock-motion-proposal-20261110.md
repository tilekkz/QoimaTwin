# Main comparison stock and motion proposal

The main `twin-v3.html` now draws moving warehouse objects using its existing
episode clock. The populated view is the default structural comparison. All
changes stay on the frontend proposal branch; shared contracts and backend run
inputs are unchanged.

## Stock

The 530 original handling units retain their source identity and provenance.
Additional goods use admitted source archetypes, dimensions, mass and native
model parts at actual slot support frames. Placement reuses cargo admission,
including slot and module payload limits. Source instance buffers are preserved.

| Structural layout | Usable slots | Original HUs | Added HUs | Visible HUs | Working vacancies |
| --- | ---: | ---: | ---: | ---: | ---: |
| A, 132 modules | 588 | 530 | 49 | 579 | 9 |
| B, 164 modules | 908 | 530 | 369 | 899 | 9 |

Both exclude 188 reserve or blocked addresses. The nine remaining usable
vacancies are reserved for the existing receiving, heavy, long and relocation
episodes; staging, conveyor ports and circulation space are not storage slots.
The 320 additional usable addresses in B explain its 320 additional goods.

This mode demonstrates each layout's capacity. Its A/B goods counts differ and
are labelled accordingly. The paid comparison retains the common original 530
HUs. The stock switch restores that common snapshot. Legacy `Only cargo` mode
uses the common snapshot exclusively; its search reads accepted B bindings and
their current `destination`, preserving immutable source `cargo.location`.

## Motion

Moving objects render on a separate layer against the cached static color and
depth. The main time, pause, reverse seek and A/B passes sample one consistent
episode. New focus buttons make the conveyor, loaded FL01 and walking S02 easy
to inspect without finding them in the warehouse overview.

- Conveyor carriers follow the source graph at 0.55 m/s with 0.8 s transfers.
  Packing waits of 42 s in A and 12 s in B are authored visual cues. A tote is
  replaced by the source parcel representation at the packing handover.
- FL01 and its original F01 driver reuse the accepted heavy inbound primitive
  for the 455 kg pallet. Attachment occurs at 60.224481402050685 s. At the main
  episode's 240 s boundary this task is still attached and incomplete; the
  source setdown at 303.92815037220765 s is outside this episode.
- S02 uses the native character gait on the admitted shared southern apron.
  The other 22 actor homes, including B's relocated pickers, are preserved.

These are finite visual demonstrations, not newly executed backend jobs. They
do not add completed jobs, savings or utilization to engine results. Full
warehouse physical workflow acceptance remains broader than this proposal.

## Verification

- Full frontend TypeScript check and production Vite build passed.
- Asset validation passed without GLB errors.
- Pure CPU checks passed: inventory scene 10, warehouse motion 24 using five
  actual source models, dynamic renderer 8, page integration 18. The source
  inventory check independently derives 579/899 and nine reserved vacancies.
- Independent peer checks covered stock admission/cleanup, native motion,
  preserved actor homes, current-destination slot lookup and B-only selection.
- A real Codex Edu parent and two own native children completed a bounded
  static review of the inventory and stock scene without confirmed findings.
- Browser checks use the actual main page, not the separate native replay page.

The old published UI evidence refers to its own source hashes and remains
historical. It is not re-labelled as acceptance of this changed page.

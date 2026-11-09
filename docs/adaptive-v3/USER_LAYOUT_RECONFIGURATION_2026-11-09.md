# Structural warehouse reconfiguration

User clarification, 2026-11-09: **«Менять секции и стеллажи»**. This extends the earlier fixed-layout cargo-slotting comparison. Reconfiguration must change actual section/rack placement and capacity; moving only cargo or drawing different outlines is insufficient.

The source warehouse remains the immutable baseline A, 144 × 72 m, with the published N2/N3 interface packet and original native models. The new structural B is a separately identified planned layout. It preserves all 530 original HU identities, quantities, masses and occupied slot identities, the same 24 workers, two vehicles, six ports and packing equipment. Original stock follows its module's rigid frame; added modules have distinct IDs and empty capacity. No model scaling or invented stock.

Every changed module, HU, picker home, zone rectangle, minimap, selection target and access path must use the same B plan. Reusing A routing after moving shelves requires renewed collision checks; unreachable or unproven movements must be refused. The earlier greedy cargo-only B remains a separate selectable mode.

This is a comparison of configurations. It does not simulate installing racks or carrying a loaded rack, and has no operational execution or relocation-cost claim. The previous C11 cost example remains separately labelled and does not price this structural change. Heavy/LONG source interfaces should remain fixed where needed to retain their existing physical admission while manual sections are rebuilt.

Confirmed source density: 132 modules occupy approximately 416 m², 4.01% of the 10,368 m² floor. Source stock occupies 530 of 588 currently unblocked slots, about 90.14%; the sparse view comes from the low number of racks, not missing inventory. A denser plan requires additional empty racks as well as changed section placement.

Current delivery remains desktop only. Target is a working tested build around 18:00 Asia/Qyzylorda; animation perfection is not a release requirement.

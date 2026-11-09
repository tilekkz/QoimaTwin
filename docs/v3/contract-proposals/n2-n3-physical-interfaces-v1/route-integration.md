# N2/N3 route-terminal interface packet

`route-terminal-interfaces.json` is an API-ready geometry proposal with explicit refusals. It does not admit W11/W12 operations, an engine run, a continuous storage transfer, or traffic scheduling. Source assets, stock, orientations, resource counts and canonical graphs remain unchanged.

It contains the exact 620-node/1,316-arc L12 graph, six port axes/service poses/apertures/policies, 17 source outbound cells and two explicit proposed IN_W_BULK cells. The two new cells at X16/X22,Z14 partition the existing two-HU ceiling. The N3 station `proposed:LONG-upper-rig-stow:IN_W:01` has one attachment-assembly place and zero HU capacity.

The 80 proposed transit connectors cover five cells × PALLET_LOAD/IBC/HEAVY_BOX/LONG_BUNDLE × loaded/empty arrival/departure. Every segment declares start/end physical poses, semantic IDs, geometry, motion direction, steering and proposal JSON pointers. Actual source service references remain intact. The new Z10 lane does not override source unloaded-only arcs. Reverse departures preserve physical yaw.

The continuous proof separates each C08 component with the original 0.25m horizontal padding, using exact trigonometric corner extrema and recursive interval bounds. All 80 connectors remain within the 144×72m floor and clear 245 bounds: 132 storage modules, 87 conveyor footprints, six packing tables, 19 staging reservations and the one stow station. Conveyor/table/reservation footprints conservatively occupy Y0..8. This is an analytic profile proof, not a native triangle sweep. Own target cells are excluded solely because intended support/contact/action needs separate native proof. Other cells and the station remain obstacles. Empty LONG retains its full cradle.

The 36 gate rows cover six original C08 loads × six ports. Port policy precedes aperture fit. IN_E_PARCEL/OUT_S_EXPRESS remain manual; IN_N_STANDARD allows powered PALLET only; OUT_W_RETAIL excludes IBC/LONG. Bare-only graph access cannot enable forbidden service. Gate geometry covers straight aligned passage through the declared open aperture; outside corridors are proposals.

The six LONG route examples preserve every exact W12 node/arc ID. Summed geometric length is not an engine KPI. Historical W12 pins a stale base fixture; its input/evidence are preserved. `current_N3_input_ref` explicitly selects the separately migrated current input SHA2aa8b23916a8a2712d3047364c9226e28a39b44235c8fd06a2057319f38eec43. It preserves all physical/input rows and six routes. All action, retention and resource guards still apply.

The 96 storage endpoint definitions expose missing graph/handling stubs instead of teleporting. Stored HUs retain module yaw, while source front-facing vehicle docks differ by π. Old C08 relative-identity profiles refuse `SAME_HU_FRAME_INCOMPATIBLE`. Explicit new relative-π variants capture the actual unchanged HU world matrix. Embedded N2 native endpoint evidence checks original fork/support contacts only; it does not admit continuous relative-π actions. Storage stubs and upper LONG retrieval stay unadmitted. M03 supports are claimed for PALLET/IBC/HEAVY; LONG needs the separate N3 support/retention interface.

IN_N_STANDARD/OUT_W_RETAIL staging and manual-port handling joins are outside these 80 connectors and return `TERMINAL_CONNECTOR_NOT_PROVED`. No extra workers, forklift pairs, receiver/shipper pools, stock, yaw flip or HU scale is invented. Full action scheduling and backend engine integration remain separate.

Offline verification from the canonical repository:

```powershell
python -X utf8 work/v3/n2-n3-route-interfaces-20261109/verify_packet.py
```

After copying the packet into the canonical proposal folder, use `--repo C:/absolute/path/to/QoimaTwin`. The verifier reads canonical sources and adjacent packet files and writes only adjacent `checks.json`. Transferable closure: `route-terminal-interfaces.json`, `reference-vehicle-graph.json`, `native-relative-pi-endpoint-evidence.json`, `route_math.py`, `verify_packet.py`, `checks.json`, `README.md`, `git-closure.json`. Generator scripts are work-only and are not runtime dependencies.

`checks.json` records positive checks and 14 negative controls, including source hashes before/after, JSON pointers, all 2,880 original L07 pose samples (zero formula difference), segment continuity/yaw/floor, real padded-profile obstruction, forbidden arcs/pairs/ports, missing/full cells, unchanged HU orientation, stale historical input and upper LONG blocks. It binds the packet SHA. `git-closure.json` lists dirty/untracked canonical dependencies for root's Git closure; it is a working-tree snapshot, not an exact-commit publication claim.

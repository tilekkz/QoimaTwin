# Motion and integration boundary

The delivered primary mode is **VISUAL DEMO / synthetic**, a scripted order in
the complete v2 geometry. It is not DES, a forecast/planner result, a queue-capacity
experiment, or evidence of savings. No operational KPI is computed in this client.
Arman owns backend, inventory ledger, business snapshots and results.

The clock samples absolute simulation seconds. Play/pause, speed, backward seek
and reset share this clock. Seek emits no old one-shots. A 300-second pallet age
timer is retained in the scripted narrative. The short belt hold is explicitly
scripted. Normal/Peak offered load is not presented as achieved throughput.

The Run v2 file adapter supports actor intervals and cell transfers. Unsupported
or missing cargo placements remain hidden with warnings. Business snapshot
payload is opaque; ledger, merge cursors, resource timers, A/B results and API
streaming are not claimed as integrated. Import compatible inline JSON using
**Открыть Run v2**. A/B is withheld until two compatible actual results exist.

Presentation is separate from operation state. Editable GLBs retain named rigid
pivots. Nearby figures and vehicles are posed then baked into shared material
surfaces; repeated distant objects use instancing and LOD. Four nearby people
receive full joint motion at once; the other people persist as visible LODs.
Wheel rotation derives from travelled distance. Drivers use the actual seat
anchor; cargo attachments use carriage/pallet anchors from exported geometry.

Standing home offsets (picker parking at X±0.65m) separate coincident contract actor points and leave the centreline clear. Idle parking faces the induction line, with carts ahead toward it, leaving the cross-aisle turn sweep clear. Packers stand
0.85m in front of their logical station root. Idle receiver R02 is drawn 1.1m
beside FI_PICK so the vehicle does not occupy the same silhouette. Idle shipper S02 is drawn1m beside the manual service corridor. These visual
offsets do not claim a collision-avoidance or pedestrian-safety model.

The conveyor retains 179 logical metre cells. Nineteen open junction decks replace
the corresponding half-module ends. Orthogonal cargo paths and cell timing are
unchanged. Passive transfer counters at packing bridge manual service gaps;
they are workstation surfaces, not additional simulated conveyor cells.

The open work carton shown during PACK is an empty presentation shell. It is
not a second parcel or an extra inventory quantity. The parcel entity appears
only at order_packed. Small item meshes represent picked lines; exact units
belong to supplied data. Receiving stacks similarly symbolize the pallet load.

Audio is original procedural WebAudio. It starts muted and unlocks on a user
gesture. Volume/category preferences persist; pause/seek/reset stop the bus.
Four voices including the loop, cooldown and accelerated summary limiting
prevent event floods. Automated checks remain silent.

| Motion | Class | Reduced behavior | Verification |
|---|---|---|---|
| Actor/cargo route interpolation | Essential | Positions and stages remain available, playback explicitly controlled | Browser smoke |
| Legs, reach, idle and head detail | Decorative | Bind/rest pose; operation status remains visible | Core + browser |
| Fork carriage/load attachment | Essential | Actual lift retained for contact and cargo support | Core + browser geometry |
| Following camera | Vestibular | Camera stays manually controlled when reduced | Browser smoke |
| Event ring/fade | Decorative | No animated ring; status text/LED retains meaning | Browser smoke |
| Floor labels / minimap | Static | Same visible IDs and viewport | Browser smoke |
| Timeline, play/pause/reset | Essential | Fully functional, no transition callback dependency | Core + browser |

Live OS preference changes are observed through matchMedia. No UI completion
depends on animation end events. Reduced motion has a visible checkbox.

The read-only [backend handoff](BACKEND_HANDOFF.md) records Arman's implemented
recorder/snapshots/chunks at `origin/arman/backend-core@5a0be9d`, the current 2.0
adapter mapping, and the exporter/API agreements remaining before integration.

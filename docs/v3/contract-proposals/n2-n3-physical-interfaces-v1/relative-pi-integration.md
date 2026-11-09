# Fixed relative-π endpoint proposal and API coherence update

The core`long-retention-interface.json` remains byte-exact SHA
`6243bba567637350b7c170ef378a1a94cc0c139da583ef80cac6a625e2432f03`.
No original C08source, stock placement, native model or root-published file was
modified. This addendum supersedes only the older prototype/type/test hashes in
the first handoff summary; prior12case evidence and code remain in
`history-before-resource-crossref/`.

`relative-pi-addon.json` defines an explicitly selected, additive profile
`long_loaded_source_frame_pi`. Its complete original HU retains a fixed
vehicle-relative quaternion`[0,1,0,0]` throughout that profile. It does not change
the original C08relative-yaw0 rule. Consumers must select the new profile and
capture the same existing HUworld transform before binding. No180degree HUworld
flip, asset rebuild, scaled bound or cargo symmetry shortcut is allowed.

The fresh bounded native proof checks70actual triangle contact pairs:

-20in the original loaded fixture at travel height with relativeHUyawπ;
-20in the separately selected27bbcorrected-cap/tyre fixture at the same pose;
-20at the historical lifted rack-removal pose, vehicleyawπ/HUworldidentity;
-6rack/HU and4fork/cradle contacts in the unchanged final source release fixture.

All geometry BIN bytes, mesh/index/material definitions, wholeHUdimensions,
200kgmass/24units and unit scale remain unchanged. Travel rotatedHUbounds remain
inside the same source envelope. The capture/rebind witness compares every actual
standaloneHUtriangle vertex occurrence: world difference at most
`1.1102230246251565e-16m`. Its lifted-rack example captures HUworldposition
`[0,.45,.225]`, worldquaternionidentity, vehicleposition`[0,0,1.625]`, yawπ.
This is a local source fixture example; a warehouse consumer must capture the
actual C04HUworld pose at its own module instance, rather than hardcode these
example coordinates. The untouched final release fixture has a deliberate20mm
cradle/HU gap and no upper rig; its rack contact is not mislabeled lower contact.

The addon is **data for a future variant-aware consumer**. Current
`sampleLongFrames(core,pose)` continues to implement relative-yaw0only and now
rejects unknown pose fields or additional selector arguments. Event preparation
likewise refuses extra variant selectors. Neither path silently returns the old
orientation for a requestedπprofile. No new variant execution API is claimed.

Resource coherence is also enforced: `required_resource_refs.operator` must equal
`command.actor_id`, and `.vehicle` must equal`command.vehicle_id`. Wrong-operator,
wrong-vehicle and crossed valid-pair negative controls refuse. Event preparation
validates state names; it does not implement a transition table, scheduler,
reservation verifier or execution. Its outcome remains unexecuted.

Reproduce the separate proof and current API checks:

```powershell
python work/v3/n3-retention-interfaces-20261109/prove-relative-pi.py
node work/v3/n3-retention-interfaces-20261109/check-interface.mjs
```

The proof takes about3seconds, uses no browser/Blender and checks all28core source
pins before/after. It does not run a continuous collision sweep, solve forces or
admit pickup, locks, keeper extraction, rig installation/stow, warehouse traffic,
backend actions or fullW12workflow. Successful native contact does not prove all
pin-cap/bridge solids clear. Original and optional models remain separate choices.

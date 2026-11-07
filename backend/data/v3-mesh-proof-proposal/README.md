# Immutable local geometry proof inputs

These seven original files (926,279 bytes) are pinned to upstream commit
`1fcb775c4b7737745130c9efa87ba18e4b52dd09`. `provenance.json` records raw SHA-256,
Git blob SHA-1 and exact byte counts. The only binary is the 818,836-byte
`forklift-pallet-low-fixture.glb`. No asset was modified or regenerated.

The two upstream Python verifier files are stored with an additional `.txt`
suffix to preserve them as source evidence, not executable backend modules.
The manifest retains their original source paths. All bound raw files disable
Git text conversion. The existing V3 operational input pin remains `22296bc`.

Run `verify_repository_pallet_fixture(Path("data/v3-mesh-proof-proposal"))`
from `app.v3.mesh_proof_fixture` to decode and independently check the actual GLB.
The backend uses its own explicit-error implementation. It never executes the
upstream Blender scripts or interprets the visual 30 seconds as engine timing.

See ADR0042 for supported geometry, numerical policy, continuous cover scope,
contact area, exact collinear GLB triangulation and operational limitations.

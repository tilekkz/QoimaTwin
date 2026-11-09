# Pinned worker source for conditional operator fit

This separate proposal package contains the original, unchanged `worker-base.glb`.
It supplements the existing pickup source without modifying protected backend data,
shared contracts or frontend assets. It grants no operation or actual initial state.

The raw file was extracted from the locally available historical Git revision
`1fcb775c4b7737745130c9efa87ba18e4b52dd09`, path
`frontend/public/models/v3/worker-base.glb`:

- Length: 181828 bytes.
- SHA-256: `c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7`.
- Git blob SHA-1: `fbdbd430af28390c18724aa61e9c4de0f028276e`.

The second authority reference is the exact existing forklift specification,
`assets/v3/specs/forklift.dimensions.json`, SHA-256
`d13741cc15e2dc4486ec880cdcbba56fe2ebf7143481d5f24be40ea31a57818b`.
Its `input_fingerprints` entry binds this worker path/hash; its `driver` section
provides the unchanged body template and seated rigid pose, and `staffing` binds
the template to existing F01/F02 actors. Operational pair selection separately
comes from the original source resource policy: outbound F02/FL02.

`provenance.json` has exact pinned canonical bytes. The verifier checks its SHA-256,
the raw worker length/SHA-256/Git blob ID, and the authenticated specification
reference. Filesystem roots are locators and are excluded from identity. No network
or Git command is needed to load the packaged bytes. The supporting historical
worker rig QA and old cab PASS are not proof inputs and are not republished here.

The worker GLB has 46 rigid nodes, 57 closed solids and 2848 triangles. The verifier
strictly decodes it and creates copied joint transforms; it does not alter the raw
asset or mesh vertices. See ADR0082 and `docs/v3/pallet-operator-fit-proposal.md`.

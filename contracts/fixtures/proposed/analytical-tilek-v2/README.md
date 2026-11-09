# Proposed visual compatibility fixture

Load `run.json` in Tilek's inline Run 2.0 file picker. This explicit visual
projection adds pallet positions and ownership, and translates forklift operations.
It preserves the source timeline, stock and metrics; it does not replace the
authoritative simulation run or declare contract 2.1 agreed.

Engine: `qoima-engine-0.4.0`; visual protocol: `tilek-visual-v1`.
Source run ID: `f231af3525b94c3904226ec78f5cd270a3ab3129ee2ad509d22ab5031961a8e4`.
Visual run ID: `d47da669d74e737b9ded87113a4580e2dde8223996e6a52aac34172234ecd8ed`.
Raw file SHA256: `3d916dabf5a85361d6337df5075167dd6fcb48d8930c5dde07f33c5267196855`.

The existing loader still ignores business snapshots, exact terminal state and
heading hints. Queue grids are explicitly unapproved proposals. See
`backend/docs/tilek-compatibility.md` for validation evidence and remaining limits.

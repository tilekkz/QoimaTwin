# ADR 0098: Pinned N2/N3 physical handoff reference adapter

Status: Accepted backend design; release verification is recorded against the exact candidate freeze.

## Context

Tilek commit `799ff93af8b082b8f1c0a40e4112b9bf8c83df11` publishes the additive
`docs/v3/contract-proposals/n2-n3-physical-interfaces-v1` packet. Its raw bundle SHA256 is
`6a8e443c4d2f8cd7f219d012fbcdae1b7533ffa1571bed76e3e2d0d6938db854`.
It supplies finite proposed N2 inlet supports/cells, signed source-HU endpoint variants,
terminal connector descriptions, and N3 retention/stow/current-input references. The upstream
packet remains `source_kind=visual_fixture`, with engine, workflow and backend-adoption flags false.
These new inputs need an authenticated backend boundary before any geometry or runtime integration.

## Decision

The separate `physical_handoff_*` modules validate reference bytes only. They do not update the old
22296/1fcb source packages, shared contracts, frontend assets, initial placement, inventory or grants.
The sole public filesystem input is an explicit caller `Path`; there is no personal fallback, fetch,
subprocess, script import, Blender, mesh execution, forecast fit, engine or HTTP operation.

`load_physical_handoff(root)` checks the fixed bundle anchor before using its manifest. It verifies
all 28 artifact raw hashes/lengths, a closed package inventory, and all 99 current source hashes.
Only canonical portable relative paths are accepted; case aliases, traversal, symlinks, junctions
and hardlinked files are refused. Unrelated files elsewhere in the source checkout are allowed:
this adapter verifies the explicitly named source subset, not the entire upstream repository.
The existing regular-file reader imposes its 128MiB per-file bound. The source root is not an identity.

The package's bundle schema is used only after its bytes have matched the anchored artifact digest.
JSON parsing rejects duplicate keys and nonfinite numbers. Schema references must be local fragments;
no network schema retrieval is admitted. Section/extension raw digests and schema identities are bound.
The three historical nested pin differences stay historical artifact content. They are not checked
against current source epochs or silently rewritten. Current authority comes from the root bundle's
99 source hashes; this is not a claim that every historical source reference is current.

An exact root-relative path can legitimately have both artifact and current-source roles. The
published packet does this for `n3-current-input.json`, `n3-historical-base.json` and
`n3-historical-route-policy.json` inside the package. Both digest relationships must agree; the
artifact byte-length requirement remains binding. One immutable physical record represents both
roles, explicitly listed in its derived report row. Counts stay28 artifacts and99 current sources,
with124 unique physical documents. Conflicting hashes and different case-aliased paths are rejected.
This corrects the initial adapter's unsupported blanket rejection of all cross-role sharing.

`PhysicalHandoff` contains only the revision, original bundle bytes, a tuple of exact frozen
`HandoffDocument(path, raw, sha256)` records, canonical descriptor bytes, and their SHA256 identity.
No parsed mutable JSON is retained as authority. `verify_physical_handoff` freshly reconstructs from
these retained immutable bytes and rejects exact-value type aliases or rehashed descriptor changes.
It intentionally does not reopen a former caller directory: a new filesystem read requires `load`.
`handoff_section` verifies first and returns a new disposable parsed copy. There is no cross-call cache.

The descriptor binds all raw records, section references, upstream flags and delivered constraints/
refusals. Backend `validation_scope=reference_only`, engine operation and operational admission remain
explicitly false. A successful adapter result certifies neither upstream geometry assertions nor
execution readiness. Published outputs contain source-relative record paths; no asset-root path
is included in their identity or success report.

## CLI and output ownership

Normal entry point:

```text
python -m app.v3.physical_handoff_cli validate --assets-root DIR --out NEW
```

The output must be new and disjoint from the input tree. An exclusive directory creation claims it
before loading input; even an existing empty directory is refused. A losing/repeated caller cannot
write failure evidence into the winning attempt. Success writes `report.json`, then `manifest.json`;
the manifest binds the report descriptor and input identity. Failure after ownership is acquired
preserves `failure.json` and any partial writes. The CLI does not copy the 127 raw source/artifact
records into output, and does not introduce a separate accepted on-disk handoff loader.

## Preserved physical limits

The proposed two M03 inlet cells and 0.18m contact frame are now explicit inputs, with synthetic
declared capacity and unchanged fixed vehicle/operator pairs. Relative pi is an explicit new profile,
never an automatic pi-as-zero normalization. The packet's 80 analytical connectors and endpoint
contacts do not clear its 96 unadmitted storage joins, continuous native motion, steering collision,
operator fit rebinding, traffic leases, action clocks or receipt ledger-credit obligations. The old
PALLET low fixture's observed steering collision remains relevant; the separate LONG variant is not
silently substituted. Source poses/IDs/limits are preserved exactly, with no inferred durations or
capacity expansion. Shared contract 2.1 adoption and full N2/N3 workflow acceptance remain separate.

## Validation boundary

Short tests construct tiny, explicitly synthetic metadata packets and monkeypatch module pins only
inside those tests. Public APIs have no hash override or skip-validation argument. Cases cover raw
anchor repinning, current source mutation, closed inventory, historical epoch retention, unsafe
paths, type aliases, schema hash/order/network references, retained reconstruction, detached parsed
copies, exclusive output ownership and preserved failures. These tests do not compile actual sources,
fit forecasts or run geometry/engines. Actual799ff93 reference-only CLI validation has separate frozen
input/code and process evidence; it does not constitute geometry or full release acceptance.

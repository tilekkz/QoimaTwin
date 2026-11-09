# V3 frozen proposal inputs

Use `from app.v3.inputs import load_v3_bundle, V3Bundle, V3InputError` and call
`load_v3_bundle(Path("data/v3-proposal"))` from the backend directory. The path is
explicit: the loader never searches another checkout, fetches a branch or uses the network.
A missing file or changed byte fails with `V3InputError`, including source path and reason.

The returned `V3Bundle` is a frozen dataclass. `source_revision` is
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`; `layout_content_hash` is
`407642632968cbd0e3f5ce1879177921c6fb7daa3292ecf375938012a0de2b71`.
`source_inventory` is a tuple of frozen `SourceInventoryEntry(path, raw_sha256, bytes)`.
`documents` is a read-only mapping keyed by original upstream relative paths, for example
`docs/v3/contract-proposals/baseline-assignment-v3.json`. Its frozen `ImmutableDocument`
values contain `canonical_bytes`; `decode()` returns a fresh mutable JSON copy.
Canonical documents use UTF-8, sorted object keys, compact separators and no nonfinite
numbers. They serve immutable access, not raw source fingerprints. Vendored upstream
bytes are preserved separately and never rewritten by ingestion.

The typed projections are tuples of frozen `SKU`, `CargoArchetype`, `HandlingUnit`,
`StorageSlot` and `Port` objects from `app.v3.input_models`. They expose core identity,
quantity, mass, dimension and capacity fields; the immutable source documents preserve
all other proposal fields, including planning legs and synthetic source statements.
`Port.seconds_by_archetype` and `open_windows` are immutable tuples. SKU HU identities
are a tuple. `baseline` is a frozen `BaselineStats` value derived from records:

| Field | Value |
| --- | ---: |
| sku_count | 200 |
| handling_units / occupied_slots | 530 / 530 |
| quantity_units | 12256 |
| gross_mass_kg | 9403.85 |
| physical_slots | 776 |
| active_slots / blocked_reserve_slots | 588 / 188 |
| free_active_slots / free_initial_flex_slots | 58 / 8 |

There are eight cargo archetypes and six ports. These values are independently checked
by tests with fixed expected arithmetic, rather than copied from an external validation
report or trusted summary. Mass is recomputed from complete archetype HU masses, with
unit contents and packaging mass identities checked first. Every SKU quantity is reconciled
with its HU identities and assignments; occupied slot and module ownership is unique.

Validation checks the exact provenance manifest digest compiled into `input_pin.py`,
revision, all 14 source sizes and raw SHA-256 hashes, strict JSON parsing (duplicate keys,
NaN/infinity and overflow rejected), and in-package source hash references. The shipped
Draft 2020-12 cargo schema validates each `cargo-catalog.records[i]`; the storage schema
validates the entire storage projection root. Only local schema references are accepted.
The loader also validates layout bindings, SKU template pointers, graph node/arc identities
and endpoints, typed slot node/local-path links, module-slot coverage, port class and shared
resource references, staging-zone links, positive capacities/service times, port mixes,
HU quantities, slot payload/clearance fit, module payload and summary conservation.

Counts, identities and byte hashes compare exactly. Geometry, unit/HU mass identities,
per-slot payload, module mass sums and capacity comparisons, and port-mix normalization
use **exact source-decimal arithmetic** (`Fraction(str(number))` before arithmetic).
Static fit uses the source C04/C05 rule `HU dimension + 2 * clearance <= usable dimension`
on every local axis, with **no epsilon**. Height .95 fits usable 1.05 with clearance .05;
.95000000001 and .9500000000000001 reject. Decimal global precision has no effect.
Source module capacities and identity local XYZ orientation remain authoritative; module
world yaw does not permit cargo rotation. Cargo storage tags and explicit slot orientation
mappings are checked, and SKU/assignment scale must be numeric one (booleans reject).
Planning legs must reference a port accepting the assigned cargo. Buffer allocations are positive
integers whose sum must equal the declared total exactly.

Only comparisons against serialized derived volumes and mass summaries retain absolute
tolerance **1e-8**, zero relative tolerance, because upstream generation serializes float
arithmetic (including volume products and module totals). These checks never grant extra
geometry or payload; module capacity uses the independent exact mass sum. Tolerance never
repairs input or changes vendored bytes. Support/handler/route admission remains separate.

`data_kind` is always `static_geometry_proposal`, `operational_admission` is always false.
No engine is run and no scheduling, operational admission, V2 stock, roles or actor homes
are imported. The pinned upstream baseline is synthetic, unclocked planning input.

The 14-file subset is enumerated in `data/v3-proposal/provenance.json`, with upstream URL,
Git blob SHA-1, raw SHA-256 and byte size. It contains the layout manifest/envelope/zones,
compiled layout links, cargo schema/catalog, SKU catalog, storage schema/slots, baseline
input/assignment, inbound/outbound ports and shared port resource policy: 10,542,460 raw
source bytes. Original bytes were checked against both inventory SHA-256 and Git blob
SHA-1 before copying. Git attributes already disable newline conversion for all files.

`excluded_sources` lists the other evidence-inventory entries. No assets or frontend files
are vendored. In particular, the semantic index, public runtime projection, storage-layout
source, conveyor/vehicle source models and visual reference assets are excluded. References
to excluded dependencies are preserved as statements, not recursively verified at runtime.
The complete layout content hash is accepted as the pinned upstream identity, **not**
independently recomputed from the excluded dependency closure. Compiled graph validation
checks internal links, not physical safety, loaded paths or scheduling. Geometry, handling,
packing/support, measured timings and a frozen execution scenario remain separate gates.

Focused checks (Python 3.12, existing environment reused):

```powershell
& D:/QoimaTwin/backend/.venv/Scripts/python.exe -m pytest tests/v3 tests/acceptance/test_analytical_timeline.py -q --tb=short
& D:/QoimaTwin/backend/.venv/Scripts/python.exe -m ruff check app/v3 tests/v3
& D:/QoimaTwin/backend/.venv/Scripts/python.exe -m mypy --platform win32 app/v3 tests/v3
& D:/QoimaTwin/backend/.venv/Scripts/python.exe -m mypy --platform linux app/v3 tests/v3
```

The Linux command checks mypy's Linux platform branches on Windows; it is not a Linux
runtime test. The coordinator owns the full suite and Linux runtime CI.

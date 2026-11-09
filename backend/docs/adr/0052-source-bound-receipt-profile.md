# ADR 0052: Compile explicit receipts without changing the source baseline

Status: accepted backend implementation decision; bounded SMALL proposal.

## Decision

A new receipt profile and compiler version extend the connected SMALL workflow
with explicit future receipt offers. The original light profile compiler, input
identity and publication format keep their current meaning. Receipt compilation
does not make an old reader understand stock creation.

The strict document uses exact integer microsecond clocks and rational choices.
It declares every receipt ID, new HU ID, known source SKU, explicit lot, full HU
quantity, arrival, inbound port and target slot. It also declares finite staging
cells, their paths and receiver IDs, plus pickup/place durations. No stock,
dimensions, mass, source port service time, graph or slot geometry override is
accepted. Boolean and floating aliases are rejected before rational reduction.
The existing pinned bundle and conveyor must match both typed facts and canonical
document bytes; an unchanged reported digest cannot certify altered source facts.

The live baseline remains 530 original HUs and 12,256 unit tokens. Future offers
remain separate from it. A disposable prospective ledger verifies receipt recipes,
full quantities, future unit placement choices and downstream orders; compilation
returns a fresh initial ledger without created receipt tokens, registered receipts,
claims or command history. The runtime credits stock only at its actual service
completion event, according to ADR0053.

## Source and physical boundaries

Only source SMALL_CARTON receipts are supported by this compiler. The selected
port must actually serve that class inbound. Its service duration and windows
come from source records; the declaration cannot replace them. Receiver identity
is restricted to the source R01/R02 pool, with explicit custody owners and all 24
worker identities preserved. Explicit actor speeds and handling durations retain
their synthetic-profile provenance rather than becoming measured source norms.

Each target is initially free, unique across declared receipts, active, manually
retrievable and compatible with SMALL cargo. The source slot supplies its actual
worker/cart anchors, dimensions, per-side clearance and payload. The compiler
checks conservative initial module mass plus all declared intact receipts against
each source module rating; it does not subtract hypothetical later picking or
reuse slots released by a future schedule. Dynamic module reallocation is outside
this first profile boundary.

Staging cells reuse the existing exact connector checks: declared port allocation,
staging bounds, buffer separation, keep-clear zones, racks, building bounds and
the complete axis-aligned swept path. Rational coordinates must be exactly
representable as finite source JSON decimals; they are never rounded to fit.
The helper now accepts a narrow read-only connector protocol; existing manual
callers and generated geometry remain unchanged.

The source walk graph omits cargo-class metadata on all 4,000 arcs. This omission
is distinct from the vehicle graph's explicit cargo whitelists. C09 defines manual
transport through pedestrian/manual-cart modes and the corresponding worker/cart
anchor; C04 permits compatible SMALL hand carry up to 15 kg. L06 requires the whole
assembly to fit, and L09's worker terminal is the manual reach anchor.

The compiler therefore applies `c09-manual-small-source-mode-projection-v1` to its
fresh decoded graph: pedestrian arcs with both cargo metadata fields absent gain
an explicit SMALL permission in the derived typed profile. Any explicit support
value or whitelist, including an empty list or a denial, is preserved. Original
source bytes, geometry, widths, modes and directed endpoints remain unchanged.
The generic graph and runtime cargo filters remain strict. The policy identifier
is part of frozen inputs, and separate mass, slot and loaded-clearance checks still
apply. This implements source schema intent rather than inferring absence as a
universal permission.

Newly generated, checked buffer arcs explicitly support only SMALL cargo.
Forward and reverse paths are separately materialized. Neither this projection
nor local connector geometry establishes hand-contact/mesh proof. A service node
itself is not a staging cell; the correct slot terminal remains its source worker
anchor rather than substituting a cart stop to evade a route failure.

## Identity and clocks

The compiler freezes normalized choices, verified source records, the derived
graph, initial stock/material state, and the separate receipt process before any
engine construction. Order-independent tables are sorted; placement sequences
remain ordered. Equivalent exact rational values normalize to one identity.
The SHA256 input identity uses canonical bytes and the new compiler version.

Every offered arrival precedes H and end is at least H. This input constraint
does not promise admission: source service must finish by the inbound cutoff,
while already admitted putaway and return may continue beyond H. The shared
runtime owns that calendar decision. Future orders use the declared putaway
address and cannot acquire units before they physically exist and are placed.

The example selects IN_E_PARCEL, DEMO_001 and the free source slot
`v3:slot:SMALL_W:017:L1:B1`, then orders three units of the received HU. Its staging
path has explicit legs 9 + 8 + 4 = 21 metres. This is a bounded source-backed
integration case, not a normal/peak workload rate, all-port execution or full V3.

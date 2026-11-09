# ADR0085 Registered storage fullness observations

Status implementation proposal awaiting composed release checks and source HTTP evidence.

ADR0080 defines exact storage occupancy, mass, volume and reservation observations from
validated coordinator results. A registered API client needs those observations bound to
the same public result it already reads.

Add `GET /api/v3/coordinator-runs/{run_id}/storage-fullness`. Resolve the known public
reference before source registration and apply the existing complete registration,
raw artifact and native journal validation. Derive the ADR0080 report using the stored
native input and result. Return its separate report identity with the public run ID,
native run ID, input hash, observed end and a versioned reader envelope.

The report retains distinct `at_horizon` and `at_end` observations. Each uses settled
state after all observed events with `tick <= T`. The end observation uses the actual
observed boundary, including for a partial result. Source capacities
come from freshly authenticated source storage descriptors. An analytical fixture
returns the existing explicit unavailable observation. Reservation counts, physical
occupancy and free active positions retain their separately defined meanings.

Ratios retain exact numerator/denominator values. An undefined denominator produces null.

Reads use the existing calculation-independent artifact reader. Unknown public IDs
return HTTP 404, unavailable or corrupt known evidence returns HTTP 500, and invalid IDs
return HTTP 422.
Each warm request verifies stored bytes before semantic reuse. A report computation
error also returns artifact_corruption. Report bytes are derived deterministically.

The new route and report version belong to this backend proposal. Existing native
run identity and publication policy remain authoritative for the underlying result.
Frontend adoption requires its own agreed mapping. Release evidence must include
positive reads, repeated deterministic reads, warm corruption checks, cold unknown
lookups and a source-bound saved-result observation.

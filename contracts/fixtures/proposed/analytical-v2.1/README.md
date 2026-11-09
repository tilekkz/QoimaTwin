# Proposed analytical Run 2.1

This is a backend proposal for Tilek, not an approved shared contract. The accepted
`contracts/run.schema.json` remains version 2.0. The existing frontend at `10496fd`
correctly rejects this proposal; use the separate Tilek visual 2.0 projection for
its current inline loader.

The matching proposed schema and transport notes are in
`backend/docs/proposals/contract-2.1/`. Engine: `qoima-engine-0.4.0`.
The analytical milestones remain handoff 32.8 s, dispatch 469 s and return 474 s.
The observation horizon is 3600 s; replay ends at 474 s.

Raw run file SHA256:
`24360d95d75f16b7a6987050968aed7079b5aff80d926e6add843505f0146b0a`.

Run identity:
`361d55b0560344a320dc673671eb457062799021ff43d50841514569358ade52`.

This fixture includes atomic cargo transitions, business snapshots, exact ticks,
physical cargo ownership and separate horizon/end metrics. Queue-grid coordinates
are explicitly marked as proposals and still require scene agreement.

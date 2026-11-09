# P01/P02 helper profile compatibility proposal

Status: authored proposal; source compilation, execution and final checks are pending.
It does not adopt a frontend contract or change the pinned source22296 baseline.

Tilek's commit `476aacb90f06e2c0785ba86288f7b7644b2a4b0f` declares exactly P01/P02 as
cross-trained packers in `frontend/public/data/v3/worker-profiles-v3.json` and
`docs/adaptive-v3/specs/P11.1.md`. Their walking speed1.2m/s and helper skill0.8 are
synthetic visual-profile choices; the source declares `engine_operation=false` and
`operational_admission=false`. No actual coordinator consumer follows from these fields.

The separate [baseline](coordinator-tilek-n4-baseline.example.json) and
[candidate](coordinator-tilek-n4-candidate.example.json) retain the mixed source experiment's
530 initial HUs,12256 units,24 actors, two unit orders, one receipt/whole shipment and
explicit clocks. Both profiles grant additional pack eligibility only to P01/P02 and
set those two actors' exact walking speed to6/5m/s. Only candidate role_intents differ
between the two complete inputs. No original experiment or historical artifact is relabeled.

P01 already participates in picking. The runtime must finish its current task, return
and release actual custody/cart resources before admitting helper work at a free station.
The proposed windows are not proof that both helpers will pack, return by the deadline,
or improve throughput. An actual comparison may be rejected, partial or not_demonstrated.

The current backend times packing through explicit station pack/clear durations. It has
no numeric worker-efficiency field. The frontend's0.8 helper skill is therefore **not**
applied or represented as quantitatively equivalent. Adding productivity coefficients
requires a separate explicit duration model, ADR and independently derived timing tests.

The source pin, shared contracts and frontend files are unchanged. This proposal aligns
two helper identities and declared walking choices only; actual native run loading,
physical contact, source workload and replay agreement remain separate work.

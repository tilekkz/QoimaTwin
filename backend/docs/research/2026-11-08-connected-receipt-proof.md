# Actual-source connected receipt and publication evidence

One optimized-Python run of `ReceiptFlowEngine` used the frozen receipt compiler
and runtime against source `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`.
The explicit example declares one 24-unit SMALL receipt, a source-compatible
initially free slot, one three-unit order and synthetic handling/material choices.
Its pre-run arithmetic was written before compilation and execution:

```text
12256 initial units + 24 credited = 12280 registered = 12277 onsite + 3 shipped
9403.85 kg source + .20 carrier + .05 parcel + .94 receipt = 9405.04 kg
9405.04 kg = 9404.885 onsite + .155 shipped
Remaining received HU = 21 * .035 kg + .10 kg wrapper = .835 kg
```

These checks passed. All 530 original wrapper identities and 24 actors were
preserved, no receipt tokens existed at tick 0, and terminal claims/resources
were clear. All workers returned to their explicit homes. S01's home is the
outbound service node in this example, so its final return distance is zero.

The native outcome was serialized as ordinary canonical JSON and read back.
The publication step reused those exact inputs and outcome without rerunning
the DES. Its strict writer and reader agreed on the entire projected run,
including actual events, inventory creation and exact H/end captures.

| Artifact or identity | Observed value |
| --- | --- |
| Input bytes | 18,093,582 |
| Input SHA256 | `259d9488c52c6c3309b5b1f1352af1521a5ea43a3b731f878ff86272229b77c7` |
| Native outcome bytes | 106,536,766 |
| Native outcome SHA256 | `ed0f380ccff79bcaa3bc6818b0cf635a9b1d35993107455aa27e3c2d34083e0d` |
| Native event SHA256 | `14a920df5558faf58b6e74e32457d3a0c1a58c8c1799f73703f66d1100c9a9b6` |
| Published receipt run ID | `2126f9494fb757a6df1a12cae3b0001c00cdfab9b167040ce4e473e8a382b7f3` |
| Published manifest SHA256 | `b10f5437118e60d0dc2f968b2351b9b0e669b46ff58402178befedd4e395a0b8` |
| Published files / bytes | 28 / 71,959,075 |

Observed timings are evidence, not newly derived test expectations: service
credit 10 s, putaway 241.76 s, receiver home 428.52 s and shipment/end 858.350002 s.
The run produced 655 events. Publication has 31 distinct captured states,
including exact H=1200 s after the earlier completed end. Inputs set endcap=2400 s.

The engine took 111.300578 s wall time and 76.843750 s CPU; the proof script took
173.528219 s. Publication/readback took 640.607542 s while other development ran.
These contended measurements are not full-shift benchmarks or performance
comparisons. They establish an executable bounded source case, not all cargo
classes, all ports, dynamic roles, continuous hand contact or frontend adoption.

Local raw evidence is retained outside Git at
`D:/QoimaTwin-runs/receipt-source-proof-20261108` and
`D:/QoimaTwin-runs/v3-connected-receipt-20261108`.
Reproduce a fresh source run with the [receipt CLI](../v3-receipt-flow.md);
do not turn the observed timestamps above into hand-derived test oracles.

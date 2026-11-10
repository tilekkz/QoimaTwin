# Actual second-account Twin UI audit

This immutable packet records audit completion only. Root review, fix acceptance and the planned 30-check browser review remain **PENDING**. It is not a complete UI, renderer, native warehouse or operational acceptance certificate.

The actual second account used requested and correlated session model **gpt-6.1-sol**, effort **xhigh**. The CLI finished in **576.89 seconds**, exit **0**, with **no timeout**. `provenance.json` contains only the requested/correlated model and session fields, execution facts and hashes. No authentication, configuration, raw transcript, launcher environment or command log is included.

The original `findings.json`, `audit.md`, `probe-results.json`, exact `component-probes.cjs` and auditor hash files are copied byte for byte. There are **2 medium and 2 low findings**, and **9 WHITE_BOX / COMPONENT_ONLY probe records**. The probe intentionally asserts the historical defects; its successful assertions are not product acceptance. It is archived verbatim with its original path assumptions and is not the portable current-source checker.

| Finding | Severity | Original evidence |
| --- | --- | --- |
| TWIN-A2-001: bubble identity and cached cause | Medium | Executed extracted component logic |
| TWIN-A2-002: selection after recovery reload | Medium | Executed extracted component logic |
| TWIN-A2-003: final keyboard presenter step | Low | Executed extracted component logic |
| TWIN-A2-004: queued sound at hide/pagehide | Low | Source-inferred in this audit; no hardware test |

## Source epochs

`source-epochs.json` preserves all seven host-launch, host-end, auditor-before and auditor-after hashes. HTML and Page changed between host launch and end. The auditor recorded a later stable epoch matching host end. **All seven files were not unchanged across the entire job.** Both launch and exact audited copies are preserved under `sources/`, with `.txt` appended and original bytes unchanged.

Navigation changed after job-end hash capture and before archival copying. Its exact audited bytes were recovered from the hash-identical immutable launch snapshot. The observed post-end hash and recovery are recorded explicitly; no current Navigation acceptance is inferred.

## Separate fix and browser work

Current source-bound component fix proofs are `docs/adaptive-v3/evidence/twin-bubbles-checks.json` (**18 cases**) and `docs/adaptive-v3/evidence/twin-page-lifecycle-checks.json` (**20 cases**). They are separate COMPONENT_ONLY evidence, not results of this second-account audit. Their source hashes and report references are bound in `W14.6.2.json`.

The holder's historical production CDP packet is separately located at `work/v3/twin-ui-old-prod-2026-11-08T17-30-18.387Z`. Any later browser confirmation of the audio defect belongs to that holder evidence and must not be represented as an executed auditor audio result. It is referenced only here, not copied or revalidated by this packaging step.

The new 30-check browser review and root fix acceptance are PENDING in this completion record. No browser, public bootstrap, WebGL, actual audio hardware, native 530-HU scene, physics/backend or operational acceptance was executed by the auditor.

`manifest.json` binds every other packet file. Its own checksum is recorded by `docs/adaptive-v3/evidence/W14.6.2.json`; no self-hash cycle is used.

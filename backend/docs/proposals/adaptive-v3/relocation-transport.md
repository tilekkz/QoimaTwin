# Bounded N1 native run transport

This opt-in transport persists an already observed, independently validated relocation run. It does not execute source DES, create a pair comparison or add a CLI/API route. The original coordinator/C65 format remains unchanged.

Use `write_relocation_run(run, out_dir, inputs=exact_frozen_bytes)` and `read_relocation_run(out_dir)` from `app.v3.relocation_transport`. Run construction and semantic authority belong to `build_relocation_run` and `validate_relocation_run`.

## Explicit namespace and complete evidence

The manifest requires transport version `qoima-relocation-run-bundle-0.1.0`, publication version `qoima-relocation-run-0.1.0` and engine version `qoima-manual-relocation-proposal-1`. It binds run ID, full input hash, common input hash and registry common hash. A coordinator manifest cannot be relabeled as relocation or accepted through a disabled version check.

The bundle contains only:

- `manifest.json`, published last;
- exact `inputs.json`;
- `catalog.json`, with closed run metadata and native outcome metadata;
- native event chunks under `events/`;
- native settled captures under `snapshots/`.

The catalog retains explicit `outcome_kind`: `relocation` or `base_noop`. A zero-job run keeps its original coordinator native payload within this separate envelope. Catalog outcome metadata cannot contain an alternate embedded event history or captured state.

## Tick boundaries and capture roles

Event chunks cover exact half-open 60,000,000-tick intervals. An event at tick60,000,000 belongs to `[60,000,000,120,000,000)`. Descriptor sequences are contiguous, every observed tick lies in its declared interval, and the native semantic reader validates event order, operations and custody.

The runtime supplies settled captures at 30,000,000-tick checkpoints, plus required H and terminal captures. Transport groups roles at the same tick into one physical capture only when their complete canonical native state agrees. Capture watermarks include every fact settled at that tick. Different same-tick checkpoint/H/end states are rejected; transport does not choose one silently.

The independent delayed hand oracle arrives at60s, uses directed2/3/5m travel at1m/s and take2/place1. H61/end-cap80 yields take64, place68 and paid return73s. The tick60 checkpoint records the admitted approaching state after all tick60 events. A65s cap retains a partial carrying state; an empty job plan preserves base no-op scope.

## File and semantic authority

The shared pure file I/O enforces exact SHA256 and raw byte lengths, canonical JSON, closed inventory, safe relative paths and rejection of filesystem aliases. The shared descriptor bounds are128MiB per referenced file,1GiB aggregate referenced bytes and a separately bounded2MiB manifest. Original descriptor validators are reused directly; the N1 manifest has its own closed fields and version gate.

The writer validates complete native semantics before publication, builds files in a temporary sibling stage and publishes the manifest last. Output must be empty or contain only the exact preexisting frozen `inputs.json`. Every created file uses exclusive creation. Repeated publication cannot overwrite an existing bundle or its input evidence.

The reader checks manifest versions/fields, raw inventory, descriptors, hashes, canonical bytes and capture/event boundaries, restores the complete native run, compares manifest/catalog identities and reruns N1 semantic validation against the exact inputs. Rehashing an altered returned tick or stock state does not authorize a new physical history.

Tests use real analytical hand engines only. Source-run transport acceptance, paired execution, frontend and API delivery remain separate work.

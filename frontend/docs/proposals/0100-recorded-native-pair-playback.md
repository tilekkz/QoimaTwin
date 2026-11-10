# ADR0100 proposal. Recorded native N1 playback

Status is proposed. This frontend-only branch starts at Tilek8437165565500ed31df4f76f583785b35d31a02b. Backend ADR0099 is the current maximum published ADR and supplies the separately versioned saved-pair read API. The backend release remains1808214.

## Source boundary

The new native-pair-v3.html page accepts qoima-saved-relocation-arm-ndjson-0.1.0 with origin verified_saved_native_pair. It keeps pair, arm, native run, native input, paired input, common input and registry identities distinct. Both arm headers must share their pair/common identities. The original warehouse fixture adapter retains its actual-engine refusal. Native records have a separate type and decoder.

The page reuses the accepted warehouse A renderer, source models, original instance matrices and createWarehouseCargo storage placement calculation. Geometry registration requires common input47ea8d54101f63b7dd2f958a41174c716607019a6f43a7379d2b80b3f42b3f99, registry753452460289b494f9e59583091245a5f1c7d2e8a2bcd28c670e4a0f620c70ab, semantic layout407642632968cbd0e3f5ce1879177921c6fb7daa3292ecf375938012a0de2b71 and raw layout eb8afaf677864983a326af6ca47f4f41fbbd6ba162613fbce078feff0128f7db. Every used node, directed arc, conveyor edge and relocation slot must resolve in that source. Both native arms use the original132-rack world. The separate structural164-rack B proposal has its own route and source authority.

## Loading and memory

Users can select two retained API response files or explicitly load the pair through the development proxy. Loading performs one bundle request per arm. Play, seek and A/B switching use local records. No requests originate from the animation loop. The API can spend several minutes authenticating each bundle, so local retained response files are supported.

Raw SHA256 and byte length are checked before JSON projection. Membership is closed against the manifest, including the omitted inputs.json descriptor. The inputs payload remains omitted. Catalog, event interval/sequence descriptors, capture tick/path/watermark and settled event cuts are correlated. Unknown members, duplicate references, incomplete streams and identity changes fail closed. ADR0099 currently provides lexically sorted members, which places catalog before captures. This ordered0.1 stream is the admitted source.

Individual decoded members are limited to4MiB, NDJSON records to6MiB and transfer bytes to192MiB per arm. The retained compact projection is limited to64MiB across both arms. Candidate loading receives the remaining budget after baseline. This bound counts encoded projected state, events and header/catalog data. Per-record parsing workspace, source geometry and GPU/model assets have separate lifetimes. The full12,256-unit inventory payload is verified as raw bytes and discarded after projecting display fields. A cache bound supplies no browser heap or performance SLO.

JSON integer tokens in native fractions retain BigInt values. Ticks, sequence numbers and byte counts remain safe integers. Fraction-to-Number conversion occurs only while producing presentation coordinates. The lossless lexer preserves JSON syntax refusal, including leading-zero integers.

## Clock and presentation

One integer microsecond clock controls Play/Pause, reset, seek, speed and A/B. The timeline ends at the common observed ceiling. Individual native status and business/resource/observation boundaries remain visible. A settled cut includes events with tick less than or equal to the chosen tick, after the selected capture watermark. Backward seek reconstructs state from the same immutable projection.

Conveyor positions use recorded BeltPose fractions, active motion intervals and the registered straight/arc geometry. Native yaw_quarters already expresses global quarter yaw. Curve angle affects position without a second heading rotation. Tote/parcel boxes are explicitly labelled presentation glyphs with conditional dimensions. Their carrier, payload and job IDs come from the native journal. A replacement reuses the same job glyph. Observed output collection removes it from the belt view.

For relocation, source custody remains until taken_tick. Actor custody lasts until placed_tick. Destination custody persists during the paid return. The native conveyor camera centres on the34 source nodes at[92.775,0.92,4.15], with span85m covering their[55.8,0.92,3] to[129.75,0.92,5.3] bounds. The relocation view uses span30m and the whole-warehouse overview remains available. The same original HU instance is transformed, with original matrices restored before each new frame and on disposal. Take/place/return timestamps retain native values. Between-boundary worker/body and carried-box coordinates are presentation interpolation along the recorded directed route, including a display carry height0.9m. These coordinates supply no hand-contact proof. S01/HU113 contact and gait/carry admission remain explicit open joins. Driver bodies are hidden because the run supplies no disembark pose. Background vehicle geometry stays at the accepted initial frame.

Complete and supported partial recordings retain their actual statuses. A partial motion lacking any recorded display endpoint is refused at playback compilation before controls activate. Planned endpoint availability never grants observed completion. No operation, resource lease, inventory event or physical admission is generated by this reader. full_n1_acceptance and operational admission remain false. The recorded paid N1 comparison retains its measured cost and result.

## Verification

The pure Node test starts with an unsupported-reader RED and then checks valid wire input, identities, raw bytes, closed membership, omitted inputs, budget refusal, exact large fractions, native JSON syntax, custody cuts, nonzero capture selection, backward seek, partial-motion refusal and clock limits. Independent review supplies additional fully repinned metadata and arc-heading controls. Real retained baseline/candidate response files provide source-schema regression inputs. Typecheck, production build and asset verification are required before owner freeze. Browser rendering and interaction evidence belongs to the separately recorded root QA.

Open the discoverable link from home-v3.html. The page starts idle and uses saved files by default. No producer or API request starts on initial page load.
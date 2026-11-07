# R09 — согласованность reference pack v3

Проверено UTC: 2026-11-07T05:36:17.212265+00:00. Исполнитель: rack_crate. Статус **VERIFY**; root решает PASS после просмотра review и HTML.

**Фактически открыты девять current concepts R01–R08/R11 и отдельный r03-common-scale.png.** Прочитаны provenance и dimension targets; все девять image hashes совпадают с provenance, все девять task cards имеют root PASS. R11 дополнительно просмотрен после закрытия coverage gap. Новых генераций, geometry или accepted PNG edits нет.

[Contact sheet](contact-sheet.html) использует неизменённые локальные PNG и открывает каждый оригинал по нажатию. HTML capture выполняет root; исполнитель не заявляет browser capture.

## Что согласовано

Крупные cuboid массы, плоские matte поверхности, небольшие ступенчатые фаски и charcoal/petrol/tan объединяют все семейства. Полки/стенки/борта/стойки/вилы имеют толщину, опоры соединены и доходят до основания. Lit pixels не являются точными shader RGB.

| Лист | Canonical use | Фактически видно |
|---|---|---|
| R01 — Art direction | Palette, cuboid primary masses, planar matte shading and small bevels. Not dimension or final equipment authority. | Large shelf, worker and forklift share thick cuboid masses, matte charcoal/petrol/tan/cream and short stepped bevels. Bottom row clearly separates blue/orange/purple/green/yellow role families; headwear and faces are a style cue, refined by R05. |
| R02 — Storage construction | Five distinct SMALL/STANDARD/HEAVY/LONG/FLEX forms and connected supports. Future C04 usable dimensions/load/accessibility govern engineering. | Five distinct labels/silhouettes: low open bins, three-deck standard rack, fork-access heavy base, three-post cantilever, finite protected FLEX footprint. Five quarter views and ten front/side insets show grounded feet, tangible shelf/arm thickness and supporting connections. |
| R03 — Cargo design | Eight stable archetype IDs and characteristic construction. Numeric X/Y/Z targets come from the separate common-scale/JSON supplement. | All eight exact cargo IDs visible; cartons, heavy handled case, strapped pallet, caged/capped/tapped IBC, elongated supported bundle, faceted drum and framed fragile crate remain distinct. LONG_BUNDLE ends are fully visible with two straps/supports; footer explicitly separates concept views from dimensions. |
| R04 — Line/packing | Continuous supported straight/turn/T transfer surfaces, pack tools and hollow tote/parcel fit. L08/C04 will fix ports and allowed payload geometry. | Straight, supported faceted 90-degree curve and open T transfer agree with their top-path insets; no transverse guard blocks the T deck. Pack worktop, lower shelf and legs join; infeed meets its edge. Foreground tote has visible interior and fitted parcel clears rim/walls visually. |
| R05 — People/roles | Dedicated four-view body construction plus five vest/headwear colors, symbols and role codes. Governs clothing over contextual figures elsewhere. | Front/side/rear/quarter preserve cuboid head, stepped headwear, torso/vest thickness, connected sleeves/hands and grounded boots. Five role variants retain dark shared shirt/trousers with colored vest/headwear and badge01/cart,02/carton,03/incoming,04/outgoing,05/forklift. |
| R06 — Forklift | Dedicated four-view chassis, four wheels, mast/carriage/two forks, seat and guard. Governs vehicle design over overview miniatures. | Four views preserve petrol chassis/tan counterweight, larger front and smaller rear wheels, guard/seat, twin mast rails, bridging carriage and exactly two connected blades. Final scale inset now has charcoal sleeves/navy trousers with yellow vest/headwear; ordinary occlusion explains invisible far wheels in some views. |
| R07 — Zones/ports | 144x72x8 intent, six named perimeter access points and two separated areas per storage type. Future accepted layout supplies executable geometry/graphs. | Three IN and three OUT IDs are readable in the main cutaway and coordinate inset; wide bulk/B2B approaches, finite staging and two areas of each storage type are visible. Bottom detail distinguishes4.5m gate clearance from8m building height; corrected role legend has the five intended hues. |
| R08 — Camera/composition | Useful overview framing and two clear close-camera compositions. Does not override role assignment, cargo size or dedicated object construction. | Warehouse overview occupies useful frame, retains six openings and differentiated low/tall/pallet/long/FLEX masses. Lower aisle and loading closeups retain volume, connected structures and human/vehicle readability; no tiny empty warehouse in a large blank canvas. |
| R11 — Picking cart | Dedicated picking-cart construction, four production angles, fitted upper-tray tote and worker/handle grip. R05 governs the contextual worker; numeric values remain synthetic design targets. | Front and rear retain the same two open trays, thick square posts, broad rear handle and supported upper-tray tote; lower tray is empty. Side shows connected yokes/grounded casters, two distinct tray heights and rear posts rising to the handle; no third shelf or detached rail. Quarter shows tray-floor/lip thickness, open under-tray air space and three visible casters; the fourth is normally occluded, not an extra wheel requirement. Top-fit inset has a continuous tan border around the tote footprint; the separate tote remains hollow and entirely supported inside the tray visually. Grip inset has a blue picker with dark sleeves/trousers; both mitten hands visibly touch the handle, elbows bend and boots meet the floor. Matte charcoal/petrol/tan cuboid construction matches R01 and R04; R05 remains the authority for worker body/headwear, while this inset specifies grip interaction. |

## Размерный authority R03 — отдельно от art

`r03-cargo.png` содержит enlarged concept cards с разной magnification. `r03-common-scale.png`/`.svg` показывают X/Y front profile при 100 px = 1 м и фигуру 1.70 м; Z задаётся отдельно. `r03-dimension-targets.json` содержит synthetic design targets, не UCI measurements. C02 должен принять их явно либо изменить с повторным reference review.

| archetype_id | X, м | Y, м | Z, м |
|---|---:|---:|---:|
| SMALL_CARTON | 0.32 | 0.24 | 0.24 |
| STANDARD_CARTON | 0.60 | 0.40 | 0.30 |
| HEAVY_BOX | 0.80 | 0.65 | 0.60 |
| PALLET_LOAD | 1.20 | 1.35 | 1.00 |
| IBC | 1.20 | 1.16 | 1.00 |
| LONG_BUNDLE | 4.20 | 0.52 | 0.65 |
| DRUM | 0.68 | 0.95 | 0.68 |
| FRAGILE_CRATE | 1.10 | 0.95 | 0.85 |

Payload/usable interior/clearance/orientation/handler не принимаются картинкой. LONG_BUNDLE 4.20 м не уменьшается scale ради STANDARD shelf. R04 tote/parcel fit не обещает, что HEAVY/PALLET/IBC/LONG являются belt payload. Storage dimensions и manual access к верхним уровням ещё требуют C/L проверки.

## R11 — закрытие dedicated-cart coverage gap

Изначально R01 давал только микротележку. Root добавил R11; теперь actual four-view PNG root PASS и независимо просмотрен R09. Во front/side/rear/quarter сохраняются два open trays, square posts, connected grounded casters, задняя broad handle и отдельная hollow tote. В верхнем лотке видна опора/clearance; нижний пуст. Обе руки в grip inset касаются ручки, ноги стоят на полу.

Synthetic target envelope W/D/H 0.72/0.92/1.00м; upper tray usable W/D 0.65/0.70м против tote OUTER base 0.60/0.40м. Это суммарный target gap 0.05 м по ширине и 0.30 м по глубине, не измерение PNG. Handle centre Y 0.98 м; upper/lower tray floors Y 0.62/0.22м; lip 0.07 м; wheel radius 0.075 м. Printed fit arrows иллюстративны и не заменяют проверку outer base/usable opening в модели. Высота tote этим target block не задаётся. R05 управляет body/headwear; малый R11 worker задаёт interaction/grip.

## Роли и IDs

R05 задаёт общий dark shirt/trousers и пять цветов vest/headwear с badges. Codes 01–05 — role design codes, не actual actor_id: picker 01 blue #3478F6/cart; packer 02 orange #F28C28/carton; receiver 03 purple #9B59D0/incoming; shipper 04 green #2AA56A/outgoing; driver 05 yellow #F4C542/forklift.

R03 содержит восемь stable archetype_id из таблицы. R04 tote/parcel — workflow containers/shipments. R07 содержит шесть proposed port IDs/XZ: IN_W_BULK(0,18), IN_N_STANDARD(72,72), IN_E_PARCEL(144,54), OUT_W_RETAIL(0,54), OUT_S_EXPRESS(48,0), OUT_E_B2B(144,18). Цвет port label не назначает uniform role.

## Конкретные противоречия, исправления и canonical scope

| ID / region | Наблюдение | Разрешение / владелец |
|---|---|---|
| H01 — R03 entire concept sheet and LONG_BUNDLE lower-middle panel | Initial global axes suggested common metric framing and LONG looked too short. | Current v2 footer says dimensions separate; elongated bundle has full ends/two straps. Separate100px/m common-scale and JSON provide X/Y/Z targets. Owner: root. State: visible_fix_rechecked. |
| H02 — R07 upper-left count; east parcel gate; lower-left gate detail; lower-right role legend | Initial inbound count/direction, gate height annotation and role legend were misleading. | Current sheet shows inbound3/outbound3, IN_E_PARCEL directed into gate,4.5m gate vs8m building, five intended role hues. Owner: root. State: visible_fix_rechecked. |
| H03 — R06 separate right-hand scale figure | Initial fully yellow jumpsuit conflicted with dark shared R05 clothing. | Final inset has dark shirt/navy trousers and yellow vest/headwear; all four vehicle views remain coherent. Owner: people_packing. State: visible_fix_rechecked. |
| C01 — R03 left scale worker; R04 PACK worker; R07 overview/people key; R08 overview workers | Context figures vary in proportions/clothing; R04 packer is all orange and R08 shows blue/purple people at tables. | R05 alone governs worker proportions, dark base clothing, role color/badge. A pictured workstation does not assign a role or event; copy no contextual jumpsuit/assignment. Owner: future people/runtime task owner. State: resolved_by_explicit_authority. |
| C02 — R03 eight enlarged hero cards vs R03 common-scale; cargo in R01/R02/R07/R08 | Hero illustrations are independently magnified; contextual stock size/count is illustrative. | Use R03 targets/common-scale as synthetic metric reference. C02 must explicitly adopt or re-review revised values; C04 usable dimensions/handling checks precede placement. Owner: future C02/C04/L09 owners. State: resolved_by_explicit_authority. |
| C03 — R04 lower tote/parcel strip | The depicted fitted parcel is a workflow shipment package, not a claim every R03 archetype fits a tote or belt. | Retain visible interior/parcel clearance intent; derive actual tote interior and allowed payload dimensions. HEAVY/PALLET/IBC/LONG require compatible handling, never arbitrary mesh scaling. Owner: future C/L/M payload and line owners. State: resolved_by_explicit_authority. |
| C04 — R04 TURN quarter/top inset; R07/R08 contextual line and vehicles | R04 has a faceted curved continuous path; overview line sketches and small vehicles are simplified. | L08 must choose matching port/centreline/clearance before modeling. Do not reuse an orthogonal replay turn cutting the inner rail; R06 supplies actual forklift design. Owner: future L08/M13/M14 owners. State: reference_scope_resolved_engineering_check_later. |
| D01 — provenance/r02.json,r04.json,r05.json,r06.json,r11.json historical status fields | Executor provenance still says VERIFY/pending while authoritative task cards are root PASS. | R09 records both facts without modifying provenance. R10 root manifest must carry authoritative PASS and distinguish historical executor snapshot status. Owner: root R10. State: nonvisual_followup_explicitly_recorded. |
| D02 — R01 tiny contextual picking cart; original R01-R08 production pack | No dedicated picking-cart production angles, fitted tote and grip inset among original eight refs. | Root created R11; current four-view PNG is root PASS and independently opened in R09. Two trays, grounded connected casters, fitted tote and both-hand grip are coherent. Dedicated cart reference coverage is now present; geometry gates remain separate. Owner: people_packing R11; rack_crate R09 follow-up; root R10. State: CLOSED_BY_R11_ROOT_PASS_AND_R09_ACTUAL_IMAGE_REVIEW. |
| C05 — R11 top-fit inset, printed dimensions and small worker-grip figure | Printed arrows span the pictured cavity rather than establishing a measured outer-base envelope; grip figure headwear/proportions remain contextual. | Use provenance synthetic targets: tote OUTER base 0.60x0.40m versus tray USABLE0.65x0.70m, and measure these in geometry. R05 governs worker body/headwear; R11 governs cart and hand-to-handle interaction. No pixel measurement or new worker design is inferred. Owner: future cart/tote/person model and rig owners. State: resolved_by_explicit_authority. |

После явного разграничения authority **не найдено незакрытого material image contradiction, требующего generation FIX**. Contextual clothing/role placement в R03/R04/R07/R08 и worker-grip inset R11 не объявляются worker production designs. R05/R06 и future adopted metric metadata остаются authoritative. D02 coverage gap закрыт actual R11 review; D01 — явный metadata follow-up R10: historical executor VERIFY не переписан этим review, root PASS подтверждён карточками.

## Доказательства и следующий gate

Полные actual SHA-256/bytes/dimensions девяти PNG, provenance hashes, dimension supplements, per-image findings и resolutions — `docs/adaptive-v3/evidence/R09.json`. HTML содержит девять concept PNG плюс один common-scale PNG без сетевых ресурсов. Source identities повторно сверены, accepted PNG/prompts/provenance не изменялись.

Root читает финальный review, открывает/captures HTML и решает R09 PASS. R09 VERIFY не разрешает geometry: R10 и relevant L/C/reference gates обязательны. Geometry, Blender, renderer/GPU и browser launch исполнителем не выполнялись.

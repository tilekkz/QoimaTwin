# QoimaTwin v3 — task board

Source: `brief/01_START_CODEX.md` + `brief/03_MICROTASKS.md`. Cards: `tasks/ID.md`.
One ACTIVE card per executor. Reviewed artifacts gate dependent work; broad parents gain children before execution.
V2 preserved; visual fixtures and backend runs have separate labels. Root alone updates central state.

| ID | Status | Owner | Dependencies | Result |
|---|---|---|---|---|
| [I01](tasks/I01.md) | PASS | root | — | Зафиксирован фактический workspace и Git baseline |
| [I02](tasks/I02.md) | PASS | rack_crate | I01 | Составлен реестр существующих моделей и исходников |
| [I03](tasks/I03.md) | PASS | root | I01 | Подготовлен снимок действующего viewer |
| [I04](tasks/I04.md) | PASS | warehouse_props | I01 | Составлена карта входов frontend/replay |
| [I05](tasks/I05.md) | PASS | root | I04 | Отделены совместные файлы и зона Армана |
| [I06](tasks/I06.md) | PASS | root | I02,I03,I04 | Записаны фактические ограничения v2 |
| [I07](tasks/I07.md) | PASS | root | I01,I02 | Создан план сохранения незавершённых исходников |
| [I08](tasks/I08.md) | PASS | root | I05,I07 | Создан журнал автономного исполнения |
| [R01](tasks/R01.md) | PASS | root | I02,I06 | Подготовлен единый style board v3 |
| [R02](tasks/R02.md) | PASS | rack_crate | R01 | Создан референсный лист пяти типов хранения |
| [R03](tasks/R03.md) | PASS | root | R01 | Создан референсный лист восьми грузовых архетипов |
| [R04](tasks/R04.md) | PASS | warehouse_props | R01 | Создан референс модульной линии и упаковочного поста |
| [R05](tasks/R05.md) | PASS | people_packing | R01,I06 | Подготовлен лист персонажей по ролям |
| [R06](tasks/R06.md) | PASS | people_packing | R01 | Создан четырёхвидовой референс forklift |
| [R07](tasks/R07.md) | PASS | root | R01 | Создан референс шести портов и разных зон здания |
| [R08](tasks/R08.md) | PASS | root | R01,R02,R07 | Подготовлен референс camera/composition для большого склада |
| [R09](tasks/R09.md) | PASS | rack_crate | R02,R03,R04,R05,R06,R07,R08,R11 | Выполнена проверка согласованности новых референсов |
| [R10](tasks/R10.md) | PASS | root | R09,R11 | Зафиксирован reference manifest v3 |
| [L01](tasks/L01.md) | PASS | warehouse_props | I05,R07 | Описана размерная оболочка 144×72×8 м |
| [L02](tasks/L02.md) | PASS | warehouse_props | L01,R02 | Подготовлен план функциональных зон |
| [L03](tasks/L03.md) | PASS | warehouse_props | L02,R07 | Заданы три входящих порта |
| [L04](tasks/L04.md) | PASS | rack_crate | L02,R07 | Заданы три исходящих порта |
| [L05](tasks/L05.md) | PASS | warehouse_props | L03,L04,R03 | Задан специализированный large gate |
| [L06](tasks/L06.md) | PASS | rack_crate | L02,L03,L04 | Построен пешеходный граф v3 |
| [L07](tasks/L07.md) | PASS | warehouse_props | L02,L03,L04,L05 | Построен транспортный граф v3 |
| [L08](tasks/L08.md) | PASS | root | L02,R04 | Описана связная conveyor topology v3 |
| [L09](tasks/L09.md) | PASS | warehouse_props | L02,L06,L07 | Размещены адреса хранения по пяти типам |
| [L10](tasks/L10.md) | PASS | warehouse_props | L06,L07,L08,L09 | Собрана инженерная preview-сцена нового layout |
| [L11](tasks/L11.md) | PASS | warehouse_props | L10 | Проверены пространственные конфликты layout |
| [L12](tasks/L12.md) | PASS | root | L11 | Зафиксирован layout manifest и его версия |
| [C01](tasks/C01.md) | PASS | warehouse_props | R03,L12 | Описана структура CargoArchetype v3 |
| [C02](tasks/C02.md) | PASS | warehouse_props | C01 | Заполнен каталог восьми архетипов |
| [C03](tasks/C03.md) | PASS | warehouse_props | C02 | Подготовлено соответствие 200 SKU архетипам |
| [C04](tasks/C04.md) | PASS | rack_crate | C01,L09 | Описана структура StorageSlot v3 |
| [C05](tasks/C05.md) | PASS | root | C02,C04 | Создана матрица совместимости типов |
| [C06](tasks/C06.md) | PASS | root | C05 | Определена проверка габаритов и ориентации |
| [C07](tasks/C07.md) | PASS | root | C05 | Определена проверка массы и обработки |
| [C08](tasks/C08.md) | PASS | root | C02,L07 | Определены ограничения движения загруженной техники |
| [C09](tasks/C09.md) | PASS | root | C06,C07,C08 | Задан порядок «совместимость, затем стоимость» |
| [C10](tasks/C10.md) | PASS | root | C03,C04,C09 | Подготовлено допустимое baseline-размещение |
| [C11](tasks/C11.md) | PASS | root | C10 | Подготовлено адаптированное размещение |
| [C12](tasks/C12.md) | PASS | root | C11,L12 | Передано предложение контрактов v3 |
| [M01](tasks/M01.md) | PASS | rack_crate | R10,C04,I09,R13.1 | Готова модель SMALL storage |
| [M02](tasks/M02.md) | PASS | warehouse_props | R10,R02,C04,I09,R13.2 | Готова модель STANDARD storage |
| [M03](tasks/M03.md) | PASS | rack_crate | R10,R02,C04,I09,R13.3 | Готова модель HEAVY storage |
| [M04](tasks/M04.md) | PASS | root_review | R10,R02,C04,C08,I09,R13.4 | Готова модель LONG storage |
| [M05](tasks/M05.md) | PASS | rack_crate | R10,R02,C04,I09,R13.5 | Готова модель FLEX storage |
| [M06](tasks/M06.md) | PASS | root | R10,R03,C02,I09 | Готово семейство SMALL/STANDARD/HEAVY cartons |
| [M07](tasks/M07.md) | PASS | root | R10,R03,R04,C02,I09 | Готово семейство tote/parcel |
| [M08](tasks/M08.md) | PASS | rack_crate | R10,R03,C02,I09 | Готова модель PALLET_LOAD |
| [M09](tasks/M09.md) | PASS | rack_crate | R10,R03,C02,I09 | Готова модель IBC |
| [M10](tasks/M10.md) | PASS | root | R10,R03,C02,I09 | Готова модель LONG_BUNDLE |
| [M11](tasks/M11.md) | PASS | root_review | R10,R03,C02,I09 | Готова модель DRUM |
| [M12](tasks/M12.md) | PASS | root | R10,R03,C02,I09 | Готова модель FRAGILE_CRATE |
| [M13](tasks/M13.md) | PASS | root | R10,R04,L08,I09 | Готов модульный комплект conveyor |
| [M14](tasks/M14.md) | PASS | root | R10,R06,C08,I09 | Готов анимируемый forklift |
| [P01](tasks/P01.md) | PASS | root | R10,R05,I09 | Готова единая базовая фигура человека |
| [P02](tasks/P02.md) | PASS | people_packing | R10,P01,R05,I09 | Готовы визуальные варианты ролей |
| [P03](tasks/P03.md) | PASS | root | R10,P02,M07,I09 | Готов комплект picker/cart |
| [P04](tasks/P04.md) | PASS | root | R10,P02,M07,P08,I09 | Готов комплект packer |
| [P05](tasks/P05.md) | PASS | root | R10,P02,M08,I09,P08 | Готов комплект receiver |
| [P06](tasks/P06.md) | PASS | root | R10,P02,M07,M08,I09,P08,M05 | Готов комплект shipper |
| [P06.1](tasks/P06.1.md) | PASS | root | R10,P02,M07,M08,I09,P08,M05 | Supported source shipper workcell and actual scan target |
| [P06.2](tasks/P06.2.md) | PASS | root | P06.1 | Connected supported parcel placement and grounded shipper motion |
| [P06.3](tasks/P06.3.md) | PASS | root | P06.2 | Clocked scan/place/idle and reviewed headless shipper kit |
| [P07](tasks/P07.md) | PASS | root | R10,P02,M14,I09 | Готов комплект driver |
| [P08](tasks/P08.md) | PASS | root | R10,R04,I09 | Готов финальный packing station |
| [P09](tasks/P09.md) | PASS | root | R10,R07,L12,I09 | Готов модульный environment/dock kit |
| [P10](tasks/P10.md) | PASS | root | R10,P03,P04,P05,P06,P07 | Подготовлен role registry и легенда |
| [P10.1](tasks/P10.1.md) | PASS | root | R10,P03,P04,P05,P06,P07 | Canonical24 actor registry and accepted role/clip bindings |
| [P10.2](tasks/P10.2.md) | PASS | root | P10.1 | Readable role legend and local staff catalogue |
| [P10.3](tasks/P10.3.md) | PASS | root | P10.2 | Reviewed staff catalogue states and current-source checks |
| [P11](tasks/P11.md) | PASS | root | R10,P10,C07 | Подготовлен WorkerProfile с навыками |
| [P11.1](tasks/P11.1.md) | PASS | root | R10,P10,C07 | Same24 immutable visual skill profiles |
| [P11.2](tasks/P11.2.md) | PASS | root | P11.1 | Explicit role/equipment/manual-mass capability gate |
| [P11.3](tasks/P11.3.md) | PASS | root | P11.2 | Reviewed skill profile inspector and complete local states |
| [W01](tasks/W01.md) | PASS | root | C12,P10 | Подготовлен детерминированный visual fixture v3 |
| [W02](tasks/W02.md) | PASS | root | W01 | Создан изолированный adapter v3 |
| [W03](tasks/W03.md) | PASS | root | W02,L06,L07 | Подключены движения по реальному графу |
| [W04](tasks/W04.md) | PASS | root | W02,M06,M07,M08,M09,M10,M11,M12 | Подключены cargo attachment и storage placement |
| [W05](tasks/W05.md) | ACTIVE | root_fullworkflow | W03,W04,P10 | Подключён единый clock действий и clips |
| [W06](tasks/W06.md) | VERIFY | root_mvp | W05 | Реализовано восстановление pause/reset/seek |
| [W07](tasks/W07.md) | TODO | unassigned | W05 | Подключены локальные VFX по событиям |
| [W08](tasks/W08.md) | VERIFY | root | W05 | Подключены управляемые SFX |
| [W09](tasks/W09.md) | TODO | unassigned | W02,C10,C11 | Готов normal/no-op сценарий |
| [W10](tasks/W10.md) | TODO | unassigned | W02,L03,L04,C11 | Готов сценарий west/east port mix shift |
| [W11](tasks/W11.md) | TODO | root | W02,C07,M08,M09 | Готов сценарий heavy inbound |
| [W12](tasks/W12.md) | READY | unassigned | W02,C08,M10,P09 | Готов сценарий long freight / large gate |
| [W12.1](tasks/W12.1.md) | PASS | account2 | W02,C08,M10,P09 | Frozen long-freight / large-gate scenario inputs |
| [W13](tasks/W13.md) | TODO | unassigned | W10,W11,W12 | Готов сценарий нескольких одновременных портов |
| [W14](tasks/W14.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13 | Готов экран slotting baseline/adapt сравнения |
| [W15](tasks/W15.md) | VERIFY | root | W06,P11 | Реализовано безопасное RoleAssignment event |
| [W16](tasks/W16.md) | VERIFY | root | W15,L06,L07 | Реализован переход к новому рабочему месту |
| [W17](tasks/W17.md) | VERIFY | root | W16,W06 | Проверено восстановление роли при seek/reset |
| [W18](tasks/W18.md) | VERIFY | root | W17,W14 | Готов отдельный N4 STAFFING comparison |
| [Q01](tasks/Q01.md) | VERIFY | account2 | M01,M02,M03,M04,M05,M06,M07,M08,M09,M10,M11,M12,M13,M14,P01,P02,P03,P04,P05,P06,P07,P08,P09 | Завершена reference/render матрица моделей |
| [Q02](tasks/Q02.md) | TODO | unassigned | Q01,P09,P10 | Выполнена браузерная проверка финальных GLB |
| [Q03](tasks/Q03.md) | PASS | root | C12,W04 | Проверена совместимость всех SKU/slots |
| [Q04](tasks/Q04.md) | TODO | unassigned | Q03,W11,W12 | Проверены ориентации и handling |
| [Q05](tasks/Q05.md) | TODO | unassigned | W03,W12,W13 | Проверены clearance и графовые маршруты |
| [Q06](tasks/Q06.md) | TODO | unassigned | W05,Q02 | Проверены контакты и захваты в clips |
| [Q07](tasks/Q07.md) | TODO | unassigned | W06 | Проверена детерминированность replay |
| [Q08](tasks/Q08.md) | TODO | unassigned | W07,W08 | Проверены SFX/VFX при ускорении |
| [Q09](tasks/Q09.md) | TODO | unassigned | W14,W18 | Проверена корректность what-if пары |
| [Q10](tasks/Q10.md) | TODO | unassigned | Q02,W14 | Измерен performance большого склада |
| [Q11](tasks/Q11.md) | TODO | unassigned | Q06,Q07,Q08,Q10 | Выполнен визуальный обзор всего сюжета |
| [Q12](tasks/Q12.md) | TODO | unassigned | Q03,Q04,Q05,Q09,Q11 | Выполнена независимая итоговая приёмка |
| [H01](tasks/H01.md) | VERIFY | root | Q12 | Собран asset manifest v3 |
| [H02](tasks/H02.md) | VERIFY | root | H01 | Собрана animation/event map |
| [H03](tasks/H03.md) | VERIFY | root | Q12 | Собран индекс visual evidence |
| [H04](tasks/H04.md) | TODO | unassigned | Q11,Q12 | Подготовлен короткий обзорный MP4 |
| [H05](tasks/H05.md) | VERIFY | root | H01,H04 | Подготовлен credits/provenance список |
| [H06](tasks/H06.md) | TODO | unassigned | H01,H02 | Подготовлена одна проверенная команда запуска |
| [H07](tasks/H07.md) | TODO | unassigned | H03,H04,H05,H06 | Подготовлен утренний README и resume checkpoint |
| [H08](tasks/H08.md) | TODO | unassigned | H07,I07 | Зафиксирована собственная поставка без потери чужих правок |
| [M06.1](tasks/M06.1.md) | PASS | warehouse_props | R10,R03,C02,I09 | Small carton: folded thin-wall tan box, centred/support origin; no duplicate oversized rim |
| [M06.2](tasks/M06.2.md) | PASS | warehouse_props | R10,R03,C02,I09 | Standard carton: different proportions and coherent folded/taped lid |
| [M06.3](tasks/M06.3.md) | PASS | warehouse_props | R10,R03,C02,I09 | Heavy case: handles, grounded fork-access base and mass/handler binding |
| [M07.1](tasks/M07.1.md) | PASS | warehouse_props | R10,R03,R04,C02,I09 | Open tote: real cavity/handles, interior exceeds parcel and payload bounds |
| [M07.2](tasks/M07.2.md) | PASS | root | R10,R03,R04,C02,I09 | Sealed parcel: paper/tape construction and verified full fit in tote |
| [M13.1](tasks/M13.1.md) | PASS | root | R10,R04,L08,I09 | Straight belt: supported transport surface and exact connection ports |
| [M13.2](tasks/M13.2.md) | PASS | root | R10,R04,L08,I09 | 90-degree turn: joined supported path and correct inside/outside cargo clearance |
| [M13.3](tasks/M13.3.md) | PASS | root | R10,R04,L08,I09 | T transfer: three open connection ends and no crossing walls |
| [P03.1](tasks/P03.1.md) | PASS | root | R10,P02,M07,I09 | Picker working figure with valid rig proportions |
| [P03.2](tasks/P03.2.md) | PASS | root | R10,P02,M07,P03.1,I09 | Picking cart with grounded wheels, clear tote tray and coherent handle |
| [P03.3](tasks/P03.3.md) | PASS | root | R10,P02,M07,P03.2,I09 | Hands and both grip anchors stay in contact with handle |
| [P03.4](tasks/P03.4.md) | PASS | root | R10,P02,M07,P03.3,I09 | Walk/cart absolute-clock gait with foot/wheel contacts |
| [P03.5](tasks/P03.5.md) | PASS | root | R10,P02,M07,P03.4,I09 | Pick action: real target/payload, hand reach and one visible transfer |
| [P03.6](tasks/P03.6.md) | PASS | root | R10,P02,M07,P03.5,I09 | Tote handoff: stable hold/deposit parent and no duplicate cargo |
| [P09.1](tasks/P09.1.md) | PASS | people_packing | R10,R07,L12,I09 | Standard dock module: thick connected frame and clear passage |
| [P09.2](tasks/P09.2.md) | PASS | people_packing | R10,R07,L12,P09.1,I09 | Large freight gate: accepted clear width/height and loaded-long envelope |
| [P09.3](tasks/P09.3.md) | PASS | people_packing | R10,R07,L12,P09.2,I09 | 144x72x8 cutaway shell, substantial walls/columns at ordinary scale |
| [P09.4](tasks/P09.4.md) | PASS | root | R10,R07,L12,P09.3,I09 | Zone/route/port markings without covering logical passage or z fighting |
| [M14.1](tasks/M14.1.md) | PASS | people_packing | R10,R06,C08,I09 | Dimension/origin/forward/anchor scheme agrees with pallet, gate and driver |
| [M14.2](tasks/M14.2.md) | PASS | people_packing | R10,R06,C08,M14.1,I09 | Body/counterweight and four connected grounded wheels, front/side check |
| [M14.3](tasks/M14.3.md) | PASS | people_packing | R10,R06,C08,M14.2,I09 | Cab/seat/guard and driver clearance, side/rear check |
| [M14.4](tasks/M14.4.md) | PASS | root | R10,R06,C08,M14.3,I09 | Twin mast, carriage and two parallel forks with functional lift connection |
| [M14.5](tasks/M14.5.md) | PASS | root | R10,R06,C08,M14.4,I09 | Matte boxy materials and all4views compared against R06 |
| [M14.6](tasks/M14.6.md) | PASS | root | R10,R06,C08,M14.5,I09 | Low/high lift pivots and pallet attachment/fork contact |
| [M14.7](tasks/M14.7.md) | PASS | root | R10,R06,C08,M14.6,I09 | Final GLB in actual browser stand: metric axes/normals/materials |
| [M14.8](tasks/M14.8.md) | PASS | root | R10,R06,C08,M14.7,I09 | Pickup/load action checked at3timestamps, no floating/interpenetration |
| [M14.9](tasks/M14.9.md) | PASS | root | R10,R06,C08,M14.8,I09 | Every child evidence read, final reference/render/browser/action integration verified |
| [W14.1](tasks/W14.1.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13 | Declare plan differences and invariant ports/staff for placement-only comparison |
| [W14.2](tasks/W14.2.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.1 | Materialize orders/receipts/stock/ports/assumptions and compare input hashes |
| [W14.3](tasks/W14.3.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.2 | Baseline is compatible and ordinary popular-near-packing comparator is included |
| [W14.4](tasks/W14.4.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.3 | Candidate passes type/dimensions/mass/handler/path before cost |
| [W14.5](tasks/W14.5.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.4 | Charge take/place/travel/resource waits/return and valid swap buffer |
| [W14.6](tasks/W14.6.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.5 | Two viewers share input clock/camera/time control without changing business inputs |
| [W14.7](tasks/W14.7.md) | VERIFY | root | W06,W09,W10,W11,W12,W13,W14.6 | Show assumptions, gain/cost and legitimate zero/negative/no-op outcome |
| [W14.8](tasks/W14.8.md) | TODO | unassigned | W06,W09,W10,W11,W12,W13,W14.7 | Correct visual/analytical/actual-run label and complete comparison evidence |
| [R11](tasks/R11.md) | PASS | people_packing | R01,R04,R05 | Dedicated picking-cart four-view reference |
| [I09](tasks/I09.md) | PASS | root | R10 | Verified V3 export and browser asset-stand pipeline |
| [I09.1](tasks/I09.1.md) | PASS | people_packing | R10 | V3 Blender helpers and numeric calibration export |
| [I09.2](tasks/I09.2.md) | PASS | root | R10 | Separate V3 browser asset stand and build entry |
| [I09.3](tasks/I09.3.md) | PASS | root | I09.1,I09.2 | Calibration GLB/source/browser integration gate |
| [P01.1](tasks/P01.1.md) | PASS | people_packing | R10,R05,I09 | Metric dimensions and named rig plan |
| [P01.2](tasks/P01.2.md) | PASS | people_packing | R10,R05,I09,P01.1 | Primary silhouette |
| [P01.3](tasks/P01.3.md) | PASS | people_packing | R10,R05,I09,P01.2 | Functional joints and support |
| [P01.4](tasks/P01.4.md) | PASS | people_packing | R10,R05,I09,P01.3 | Materials, face and badge |
| [P01.5](tasks/P01.5.md) | PASS | people_packing | R10,R05,I09,P01.4 | Four-view reference comparison and fixes |
| [P01.6](tasks/P01.6.md) | PASS | people_packing | R10,R05,I09,P01.5 | Final GLB and actual browser stand |
| [P01.7](tasks/P01.7.md) | PASS | people_packing | R10,R05,I09,P01.6 | Base articulation and parent integration gate |
| [P08.1](tasks/P08.1.md) | PASS | rack_crate | R10,R04,I09 | Metric frame/worktop/transfer interface plan |
| [P08.2](tasks/P08.2.md) | PASS | rack_crate | R10,R04,I09,P08.1,L08 | Frame, legs and worktop geometry |
| [P08.3](tasks/P08.3.md) | PASS | rack_crate | R10,R04,I09,P08.2 | Scanner, printer, screen and tape details |
| [P08.4](tasks/P08.4.md) | PASS | rack_crate | R10,R04,I09,P08.3 | Pivots, payload and work interfaces |
| [P08.5](tasks/P08.5.md) | PASS | rack_crate | R10,R04,I09,P08.4 | Four-view comparison and corrections |
| [P08.6](tasks/P08.6.md) | PASS | rack_crate | R10,R04,I09,P08.5 | Final GLB/browser and parent gate |
| [R12](tasks/R12.md) | PASS | rack_crate | R03,R06,L05,R10 | Independent long-load cradle reference before attachment mesh |
| [L12.1](tasks/L12.1.md) | PASS | warehouse_props | L11 | Versioned semantic index and source identity map |
| [L12.2](tasks/L12.2.md) | PASS | warehouse_props | L12.1 | Compile local graph connections without losing shared edge splits |
| [L12.3](tasks/L12.3.md) | PASS | warehouse_props | L12.2 | Stable manifest checksums and isolated frontend data package |
| [H08.1](tasks/H08.1.md) | PASS | rack_crate | I05 | Independent preserved V2 runnable package |
| [R13.1](tasks/R13.1.md) | PASS | rack_crate | R02,R10,L09 | SMALL independent four-view production reference |
| [R13.2](tasks/R13.2.md) | PASS | root | R02,R10,L09 | STANDARD independent four-view production reference |
| [R13.3](tasks/R13.3.md) | PASS | rack_crate | R02,R10,L09 | HEAVY independent four-view production reference |
| [R13.4](tasks/R13.4.md) | PASS | root | R02,R10,L09 | LONG independent four-view production reference |
| [R13.5](tasks/R13.5.md) | PASS | root | R02,R10,L09 | FLEX independent four-view production reference |
| [R13](tasks/R13.md) | PASS | root | R02,L09 | Dedicated four-view storage construction pack |
| [M14.6.1](tasks/M14.6.1.md) | PASS | root | R10,R06,C08,I09,M14.5 | Final vehicle with real lock bores and native pallet lift contacts |
| [M14.6.2](tasks/M14.6.2.md) | PASS | root | R10,R06,C08,I09,M14.6.1,M04,M10 | Actual LONG base/pins and separate upper bundle restraints |
| [M14.6.3](tasks/M14.6.3.md) | PASS | root | R10,R06,C08,I09,M14.6.1,M14.6.2,M08,M09,M11,M12 | All six native loaded assemblies and low/high interface gate |
| [P03.5.1](tasks/P03.5.1.md) | PASS | root | P03.4,P01.7,P02 | Manual picker wrist roll and closing mitten controls |
| [P03.5.2](tasks/P03.5.2.md) | PASS | root | P03.5.1,M06.1,M01 | Native open partial SMALL case and primary-unit source fixture |
| [P03.5.3](tasks/P03.5.3.md) | PASS | root | P03.5.2,FIX01.3,P03.5.1.1 | Reach, pick primary units, withdraw and deposit without duplication |
| [FIX01.1](tasks/FIX01.1.md) | PASS | root | — | Inward neutral palms on both worker templates |
| [FIX01.2](tasks/FIX01.2.md) | PASS | root | FIX01.1 | Top-down cart grip and affected pose regressions |
| [FIX01.3](tasks/FIX01.3.md) | PASS | root | FIX01.2 | Four-flap outer SMALL carton opening |
| [P03.5.1.1](tasks/P03.5.1.1.md) | PASS | root | P03.5.1,FIX01.2 | Explicit manual overhead reach controls |
| [P04.1](tasks/P04.1.md) | PASS | root | R10,P02,M07,P08,I09 | Metric packing workcell and contact poses |
| [P04.2](tasks/P04.2.md) | PASS | root | P04.1 | Absolute-clock final seam press, idle and blocked actions |
| [P04.3](tasks/P04.3.md) | PASS | root | P04.2 | Packer runtime, seek and reference review |
| [P03.5.3.1](tasks/P03.5.3.1.md) | PASS | root | P03.5.2 | Independent compact manual gripper reference and metric plan |
| [P03.5.3.2](tasks/P03.5.3.2.md) | PASS | root | P03.5.3.1 | Native compact gripper, linked jaw travel and browser views |
| [P03.5.3.3](tasks/P03.5.3.3.md) | PASS | root | P03.5.3.2 | Clocked tool-assisted extract, withdraw, carry and tote deposit |
| [P03.5.3.3.1](tasks/P03.5.3.3.1.md) | PASS | root | P03.5.3.2,P03.5.1 | Raw-body-preserving picker thumb-press derivative |
| [P05.1](tasks/P05.1.md) | PASS | root | R10,P02,M08,P08,I09 | Receiving workcell and real scan target |
| [P05.2](tasks/P05.2.md) | PASS | root | P05.1,P01.7 | Connected receive confirmation and inward idle poses |
| [P05.3](tasks/P05.3.md) | PASS | root | P05.2 | Clocked scan/receive/idle runtime and reviewed headless kit |
| [W02.1](tasks/W02.1.md) | PASS | root | W01 | Typed source-bound V3 fixture/layout adapter |
| [W02.2](tasks/W02.2.md) | PASS | root | W02.1 | Connected local V3 warehouse viewer and complete load states |
| [W03.1](tasks/W03.1.md) | PASS | root | W02,L06,L07 | Filtered canonical graph router and source-bound C08 policy |
| [W03.2](tasks/W03.2.md) | PASS | root | W03.1 | Exact analytic vehicle and canonical pedestrian route sampling |
| [W03.3](tasks/W03.3.md) | PASS | root | W03.2 | Connected muted route preview and reviewed scene admission states |
| [W04.1](tasks/W04.1.md) | PASS | root | W02,C06,C07,C08 | Single-parent cargo state and immutable placement admission |
| [W04.2](tasks/W04.2.md) | PASS | root | W04.1 | Actual shared cargo instances and physical storage placement |
| [W04.3](tasks/W04.3.md) | PASS | root | W04.2,W03,P10,P11,M14,P03 | Connected actor vehicle cart and belt support anchors |
| [W09.1](tasks/W09.1.md) | PASS | scenario_inputs | W02,C10,C11 | Frozen preregistered scenario input and paired source identity |
| [W09.2](tasks/W09.2.md) | TODO | root | W09.1,W05,W06 | Connected scenario actions replay and no-op or shift acceptance |
| [W10.1](tasks/W10.1.md) | PASS | scenario_inputs | W02,L03,L04,C11 | Frozen preregistered scenario input and paired source identity |
| [W10.2](tasks/W10.2.md) | TODO | root | W10.1,W05,W06 | Connected scenario actions replay and no-op or shift acceptance |
| [W11.1](tasks/W11.1.md) | PASS | account2 | W02,C07,M08,M09 | Frozen heavy-inbound input pair and independent admission/source checks |
| [W05.1](tasks/W05.1.md) | PASS | action_timeline | W03,W04,P10,P11 | Source-bound absolute action timeline and exclusive resource intervals |
| [W05.2](tasks/W05.2.md) | PASS | action_walking | W05.1 | Grounded canonical worker walking and action-frame bindings |
| [W05.3](tasks/W05.3.md) | VERIFY | root_light_join | W05.2 | Light cargo pick/pack joins with complete units and support |
| [W05.4](tasks/W05.4.md) | VERIFY | root_pallet_review | W05.1 | Loaded forklift physical joins and route/resource admission |
| [W05.4.3](tasks/W05.4.3.md) | PASS | transfer_applicator | W05.4.1,W04,P07 | Same-instance native pallet transfer applicator |
| [W05.4.2](tasks/W05.4.2.md) | PASS | account2 | W05.4.1,W04,P07 | Native same-pallet transfer geometry gate |
| [W05.4.1](tasks/W05.4.1.md) | PASS | pallet_plan_fix | W05.1,W03,W04,M14.8,P07 | Source-bound single-pallet transfer plan and absolute phases |
| [W05.5](tasks/W05.5.md) | TODO | unassigned | W05.3,W05.4 | Unified scene clock integration for walk pick pack load |
| [W05.5.1](tasks/W05.5.1.md) | PASS | root | W05.1,W04 | Browser-deployable verified action source reader |
| [P05.4](tasks/P05.4.md) | PASS | receiver_elbow | P05.3 | Natural receiver elbow branch and complete trajectory |
| [P06.4](tasks/P06.4.md) | PASS | shipper_elbow | P06.3 | Natural shipper elbow branch and complete trajectory |
| [W05.4.4](tasks/W05.4.4.md) | PASS | root | W05.4.1,W05.5.1 | Reversible same-pallet demonstration in actual warehouse scene |
| [W14.6.1](tasks/W14.6.1.md) | PASS | defense_ui | W02,W05.4.4 | Review current demonstrational Twin controls and defense walkthrough |
| [W14.6.2](tasks/W14.6.2.md) | PASS | account2_twin_ui | W02 | Independent second-account audit of current Twin UI lifecycle and semantics |
| [W05.3.1](tasks/W05.3.1.md) | PASS | base_carry_pose | W05.2,W04 | Native whole-HU grip calibration on the existing P02 worker-base rig |
| [W14.6.3](tasks/W14.6.3.md) | PASS | support_shell | W02 | Preserve mobile contextual navigation and keyboard focus in the shared V3 shell |
| [W05.3.2](tasks/W05.3.2.md) | PASS | account2_base_carry | W05.2 | Independent actual second-account review of native P02 carry calibration |
| [W05.3.3](tasks/W05.3.3.md) | PASS | root_loaded_calibration | W05.3.1,W05.2 | Native pre-held P02/base loaded-walk calibration with one whole HU |
| [W05.3.4](tasks/W05.3.4.md) | PASS | dynamic_cargo_binding | W04.2,W05.3.1 | World-preserving native HU render-binding handoff for precise loaded motion |
| [W05.3.5](tasks/W05.3.5.md) | PASS | account2_pickup_feasibility | W05.3.1,W04.2 | Independent native source-grip feasibility for an upper SMALL stock unit |
| [W05.3.6](tasks/W05.3.6.md) | PASS | account2_source_torso_grip | W05.3.1,W05.3.5 | Native upper-stock source-grip endpoint with original torso freedom |
| [W11.2](tasks/W11.2.md) | VERIFY | root_mvp | W11.1.1,W05,W06 | Connected heavy-inbound actions and source-identical comparison |
| [W11.1.1](tasks/W11.1.1.md) | PASS | heavy_scenario_inputs | W11.1 | Current-source heavy-inbound pair with explicit source-epoch compatibility |
| [W05.3.7](tasks/W05.3.7.md) | PASS | root_natural_stance | W05.3.3 | Natural carry cadence and grounded double-support calibration |
| [W05.3.8](tasks/W05.3.8.md) | FIX | account2_cart_release | P03.5.3.3,W04.3 | Native manual-picker cart hand-release calibration without pose snap |
| [W05.3.9](tasks/W05.3.9.md) | FIX | account2_cart_natural_grip | W04.3 | Corrected natural original-manual cart-grip arm calibration |
| [W05.3.7.1](tasks/W05.3.7.1.md) | PASS | root | W05.3.7 | Ship portable project page for natural character-motion review |
| [W05.3.10](tasks/W05.3.10.md) | PASS | root | W05.3.7 | Lower and closer natural P02 box hold requested by user |
| [W05.3.11](tasks/W05.3.11.md) | PASS | root | W05.3.7 | Subtle deterministic breathing with planted feet and preserved hand contact |
| [W05.3.12](tasks/W05.3.12.md) | PASS | root | W05.3.10,W05.3.11 | Lower P02 box hold with vertical upper arms and approximately 90 degree elbows |
| [W05.3.13](tasks/W05.3.13.md) | PASS | root | W05.3.12 | Convincing close whole-palm box grasp with restored natural arm volume |
| [W12.2](tasks/W12.2.md) | PASS | root | W02,C08,M10,P09 | Native pre-held LONG gate calibration with driver and rolling |
| [W19](tasks/W19.md) | PASS | root | — | Structural section and rack reconfiguration B with preserved source inventory |

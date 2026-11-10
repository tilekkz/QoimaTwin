# Реестр существующих моделей — I02

Снимок UTC: 2026-11-07T04:49:43.045741+00:00. Статус: **VERIFY**, решение PASS принимает лид.

Инвентаризация прочитала фактические файлы: **23 V2 модели** (21 runtime family, calibration и master) и **10 legacy моделей**. GLB/.blend/build entry присутствуют у всех 33. Полные SHA-256, bytes, mtime и пути всех источников/референсов — в [asset-inventory.json](evidence/asset-inventory.json). Это сохранённый V2 baseline, не приёмка нового V3 и не новый visual/runtime PASS.

## Как читать реестр

Все пути относительно корня проекта. `✓` — файл найден и прочитан. В столбцах GLB/.blend указаны фактические bytes и первые 12 символов SHA-256; JSON содержит полные 64 символа для каждого файла, включая builders, helpers, prompts и изображения.

Независимый concept — ранее сгенерированный imagegen лист с сохранённым prompt. Source renders/browser captures/contact sheets — производные изображения построенного объекта. Нахождение изображения в `assets/references` не меняет его происхождение.

## V2 namespace: frontend/public/models/v2

| Asset | GLB: путь / bytes / SHA256[0:12] | .blend: путь / bytes / SHA256[0:12] | Build entry | Независимый concept |
|---|---|---|---|---|
| buffer-pallet | ✓ `frontend/public/models/v2/buffer-pallet.glb`<br>98432 / `2673797191a1` | ✓ `assets/v2/blender/buffer-pallet.blend`<br>143836 / `18abcac49ee5` | ✓ `tools/blender/v2/build_equipment.py` | ✓ `assets/references/buffer-pallet.png` |
| calibration-v2 | ✓ `frontend/public/models/v2/calibration-v2.glb`<br>615992 / `477ad713ddff` | ✓ `assets/v2/blender/calibration-v2.blend`<br>348069 / `624d5f12ef10` | ✓ `tools/blender/v2/export_calibration_v2.py` | Нет отдельного: metric fixture / assembly (N/A) |
| conveyor-corner | ✓ `frontend/public/models/v2/conveyor-corner.glb`<br>103520 / `08cce830e2b4` | ✓ `assets/v2/blender/conveyor-corner.blend`<br>120878 / `d4d067d20377` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/conveyor.png` |
| conveyor-diverter | ✓ `frontend/public/models/v2/conveyor-diverter.glb`<br>113156 / `eb521a8c44e9` | ✓ `assets/v2/blender/conveyor-diverter.blend`<br>123234 / `71e94c8d03a0` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/conveyor.png` |
| conveyor-high | ✓ `frontend/public/models/v2/conveyor-high.glb`<br>72904 / `b69e07bc33b3` | ✓ `assets/v2/blender/conveyor-high.blend`<br>119295 / `4717f0363236` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/conveyor.png` |
| conveyor-low | ✓ `frontend/public/models/v2/conveyor-low.glb`<br>14484 / `a2365a420531` | ✓ `assets/v2/blender/conveyor-low.blend`<br>104992 / `bb27c4850fa9` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/conveyor.png` |
| crate | ✓ `frontend/public/models/v2/crate.glb`<br>37940 / `8ef34297d072` | ✓ `assets/v2/blender/crate.blend`<br>112526 / `df9fa6b7317f` | ✓ `tools/blender/v2/build_equipment.py` | ✓ `assets/references/crate-reference.png` |
| dock | ✓ `frontend/public/models/v2/dock.glb`<br>141336 / `db00861d5461` | ✓ `assets/v2/blender/dock.blend`<br>138095 / `0c36f9ba7b1c` | ✓ `tools/blender/v2/build_storage_environment.py` | ✓ `assets/references/v2/large-environment-reference.png` |
| driver | ✓ `frontend/public/models/v2/driver.glb`<br>205224 / `537c33cdda72` | ✓ `assets/v2/blender/driver.blend`<br>153832 / `529d7ed1d2bc` | ✓ `tools/blender/v2/build_personnel.py` | ✓ `assets/references/v2/driver.png` |
| environment-shell | ✓ `frontend/public/models/v2/environment-shell.glb`<br>925428 / `e0ce59bbdbce` | ✓ `assets/v2/blender/environment-shell.blend`<br>353874 / `d9014732d436` | ✓ `tools/blender/v2/build_storage_environment.py` | ✓ `assets/references/v2/large-environment-reference.png` |
| forklift | ✓ `frontend/public/models/v2/forklift.glb`<br>883864 / `77f053652628` | ✓ `assets/v2/blender/forklift.blend`<br>229509 / `0a9f05d8da40` | ✓ `tools/blender/v2/build_equipment.py` | ✓ `assets/references/forklift.png` |
| large-warehouse | ✓ `frontend/public/models/v2/large-warehouse.glb`<br>5199172 / `b479cf638298` | ✓ `assets/v2/blender/large-warehouse.blend`<br>2401950 / `d96117b316af` | ✓ `tools/blender/v2/assemble_large_warehouse.py` | Нет отдельного: metric fixture / assembly (N/A) |
| order-tote | ✓ `frontend/public/models/v2/order-tote.glb`<br>88452 / `3a98e98805db` | ✓ `assets/v2/blender/order-tote.blend`<br>114885 / `eac1461cb5ed` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/order-tote.png` |
| packing-station | ✓ `frontend/public/models/v2/packing-station.glb`<br>372160 / `530241ecfc96` | ✓ `assets/v2/blender/packing-station.blend`<br>185304 / `b137458badc9` | ✓ `tools/blender/v2/build_equipment.py` | ✓ `assets/references/packing-station-reference.png` |
| pallet | ✓ `frontend/public/models/v2/pallet.glb`<br>170988 / `eaf169859c7a` | ✓ `assets/v2/blender/pallet.blend`<br>124002 / `6ce577241a13` | ✓ `tools/blender/v2/build_equipment.py` | ✓ `assets/references/buffer-pallet.png` |
| picker-worker | ✓ `frontend/public/models/v2/picker-worker.glb`<br>214584 / `6adbf8e51622` | ✓ `assets/v2/blender/picker-worker.blend`<br>156906 / `5b3191e8c82e` | ✓ `tools/blender/v2/build_personnel.py` | ✓ `assets/references/v2/standing-worker.png` |
| picking-cart | ✓ `frontend/public/models/v2/picking-cart.glb`<br>263944 / `82a2a3ba1602` | ✓ `assets/v2/blender/picking-cart.blend`<br>146786 / `616495c7f387` | ✓ `tools/blender/v2/build_personnel.py` | ✓ `assets/references/picker-cart-reference.png` |
| rack-high | ✓ `frontend/public/models/v2/rack-high.glb`<br>265980 / `15fc4686d735` | ✓ `assets/v2/blender/rack-high.blend`<br>159251 / `ac29ac6bd66f` | ✓ `tools/blender/v2/build_storage_environment.py` | ✓ `assets/references/v2/tall-rack-reference.png` |
| rack-low | ✓ `frontend/public/models/v2/rack-low.glb`<br>26768 / `992b12305c83` | ✓ `assets/v2/blender/rack-low.blend`<br>117199 / `5534d8cfa753` | ✓ `tools/blender/v2/build_storage_environment.py` | ✓ `assets/references/v2/tall-rack-reference.png` |
| sealed-parcel | ✓ `frontend/public/models/v2/sealed-parcel.glb`<br>34908 / `75878e431123` | ✓ `assets/v2/blender/sealed-parcel.blend`<br>114098 / `05327afb8968` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/sealed-parcel.png` |
| standing-worker | ✓ `frontend/public/models/v2/standing-worker.glb`<br>210996 / `d2aaec73edb1` | ✓ `assets/v2/blender/standing-worker.blend`<br>156014 / `aaab68ba87ab` | ✓ `tools/blender/v2/build_personnel.py` | ✓ `assets/references/v2/standing-worker.png` |
| tote-low | ✓ `frontend/public/models/v2/tote-low.glb`<br>5564 / `9a817395e2a9` | ✓ `assets/v2/blender/tote-low.blend`<br>101817 / `f25e905a8f46` | ✓ `tools/blender/v2/build_logistics.py` | ✓ `assets/references/v2/order-tote.png` |
| worker-low | ✓ `frontend/public/models/v2/worker-low.glb`<br>62612 / `a160685ba51e` | ✓ `assets/v2/blender/worker-low.blend`<br>123787 / `5294c9522b24` | ✓ `tools/blender/v2/build_personnel.py` | ✓ `assets/references/v2/standing-worker.png` |

## Legacy namespace: frontend/public/models

| Asset | GLB: путь / bytes / SHA256[0:12] | .blend: путь / bytes / SHA256[0:12] | Build entry | Независимый concept |
|---|---|---|---|---|
| buffer-pallet | ✓ `frontend/public/models/buffer-pallet.glb`<br>96848 / `cd0d2b7e664f` | ✓ `assets/blender/buffer-pallet.blend`<br>119499 / `6a8f5074f1a9` | ✓ `tools/blender/build_buffer_pallet.py` | ✓ `assets/references/buffer-pallet.png` |
| calibration | ✓ `frontend/public/models/calibration.glb`<br>2548 / `8c0581337625` | ✓ `assets/blender/calibration.blend`<br>93243 / `2a23a8082223` | ✓ `tools/blender/export_calibration.py` | Нет отдельного: metric fixture / assembly (N/A) |
| crate | ✓ `frontend/public/models/crate.glb`<br>39752 / `fb86e4cd950c` | ✓ `assets/blender/crate.blend`<br>108832 / `b53cc34a8407` | ✓ `tools/blender/build_crate.py` | ✓ `assets/references/crate-reference.png` |
| environment | ✓ `frontend/public/models/environment.glb`<br>838084 / `c86090f6c2e6` | ✓ `assets/blender/environment.blend`<br>250104 / `c2b6b91d0ca3` | ✓ `tools/blender/build_environment.py` | ✓ `assets/references/environment.png` |
| forklift | ✓ `frontend/public/models/forklift.glb`<br>748184 / `642a277a418f` | ✓ `assets/blender/forklift.blend`<br>214864 / `f64a780bd48a` | ✓ `tools/blender/build_forklift.py` | ✓ `assets/references/forklift.png` |
| ibc-tote | ✓ `frontend/public/models/ibc-tote.glb`<br>361256 / `99e244adbda9` | ✓ `assets/blender/ibc-tote.blend`<br>163347 / `bab9a1228d0a` | ✓ `tools/blender/build_ibc_tote.py` | ✓ `assets/references/ibc-tote.png` |
| packing-station | ✓ `frontend/public/models/packing-station.glb`<br>212620 / `cc296b95b106` | ✓ `assets/blender/packing-station.blend`<br>140718 / `9798aa220837` | ✓ `tools/blender/build_packing_station.py` | ✓ `assets/references/packing-station-reference.png` |
| picker-cart | ✓ `frontend/public/models/picker-cart.glb`<br>408652 / `4a77988ea18f` | ✓ `assets/blender/picker-cart.blend`<br>174362 / `07a8615abac9` | ✓ `tools/blender/build_picker_cart.py` | ✓ `assets/references/picker-cart-reference.png` |
| rack-bay | ✓ `frontend/public/models/rack-bay.glb`<br>221952 / `a1002c910586` | ✓ `assets/blender/rack-bay.blend`<br>152797 / `5703884958df` | ✓ `tools/blender/build_rack_bay.py` | ✓ `assets/references/rack-bay-reference.png` |
| warehouse | ✓ `frontend/public/models/warehouse.glb`<br>3066736 / `5c76da9fc0c6` | ✓ `assets/blender/warehouse.blend`<br>1251188 / `4901bd4db7ab` | ✓ `tools/blender/assemble_warehouse.py` | Нет отдельного: metric fixture / assembly (N/A) |

## Источники и происхождение

Четыре актуальных V2 builders: `build_storage_environment.py` (4), `build_logistics.py` (7), `build_personnel.py` (5), `build_equipment.py` (5); ещё `export_calibration_v2.py` и `assemble_large_warehouse.py`. Пути находятся в `tools/blender/v2/`. Действительные import/output dispatch прочитаны из текущих файлов, с номерами строк в JSON. Shared helpers `v2_common.py`/`../asset_common.py` и legacy source imports оборудования перечислены для каждого asset.

V2 equipment сохраняет отдельные V1 sources: `build_forklift.py`, `build_packing_station.py`, `build_buffer_pallet.py`, `build_crate.py`. Их наличие не означает, что V1 GLB перезаписаны. Assembly/calibration используют GLB компонентов; это зависимые сборки, а не отдельный concept design.

| Класс reference | Файлов | Значение |
|---|---:|---|
| Независимые generated concepts | 15 | 8 legacy + 7 V2; каждому найден prompt |
| Runtime screenshots внутри assets/references/v2 | 10 | personnel-* contact/action evidence; не concept |
| Accepted V3 references | 0 | Новая фаза R ещё не выполнена |

Все concept/prompt/screenshot пути и их фактические bytes/SHA-256 находятся в `reference_catalog`/`file_catalog` JSON. Для 21 V2 семейства также записаны 4 source views, 4 browser views и обе comparison sheets; для 8 legacy props — 4 source views. Их перечисление не является повторной визуальной приёмкой.

## Найдено / отсутствует / оговорки

- Все 33 GLB и 33 editable .blend найдены; все build entry/helper/reference/prompt пути присутствуют.
- Сверка 23 V2 entries с текущим manifest: совпадают bytes/SHA-256 GLB, .blend, build sources и concepts.
- Dedicated concept отсутствует по назначению у `v2:calibration-v2`, `v2:large-warehouse`, `legacy:calibration`, `legacy:warehouse`; общие component references не подменяют отдельный лист.
- `assets/blender/calibration.stats.json` не найден: legacy calibration exporter не создаёт этот sidecar. GLB, .blend и source exporter найдены.
- Старый tall-rack concept/prompt описывает 5.4 м; текущий V2 physical rack 4.65 м и logical envelope 5.4 м различаются явно. Старые картинки не задают физику V3.
- Существующие `.blend1` сохранены и перечислены отдельно в JSON для I07; inventory не создавал backup и ничего не удалял.

## Классификация переиспользования в V3

| Семейство | Что полезно сохранить | Что требует нового reference gate |
|---|---|---|
| Storage / shell / dock | Конструктивные primitives, anchors и различие logical/physical envelope |144×72×8, пять типов хранения, шесть портов, новый blocky силуэт |
| People / cart / driver | Joint naming, seat/grip/foot contacts, физический масштаб | Квадратные cartoon формы, 5 контрастных ролей, badge/legend |
| Conveyor / packing | Canonical module ports, open junction topology, transfer/contact conventions | Новая согласованная modular reference и geometry/style checks |
| Cargo / forklift / pallet / IBC | Реальные размеры, origin/pivots, механизм установки | Восемь разных архетипов, допустимый handler, ориентация и clearance |
| Calibration / master | Метрические fixture patterns, semantic IDs, assembly approach | Пересобрать из принятых V3 компонентов; не масштабировать весь V2 master |

Ни один существующий asset или concept не объявлен автоматически принятым для V3. `v3_reuse` записан отдельно у всех 33 моделей.

## Проверка и пределы evidence

Filesystem enumeration и GLB JSON metadata проверяют количество и namespace. Прямое чтение bytes и SHA-256 проверяет наличие и идентичность. Кодовые mapping/import fragments проверены текущим source fallback: граф `qoima-twin`, поколение 2026-11-06T22:22:36Z, 18 paths без recorded issues, freshness `metadata_changed`; это не доказательство актуальности графа. Индекс не обновлялся.

I02 не запускал Blender, renderer, GPU, viewer или model tests. Внутреннее качество .blend и новые V3 visual gates этим реестром не подтверждаются. Проверенные dirty changes I01 сохранены. Следующий зависимый шаг I07 — отдельный verified backup, который выполняет лид.

Повторная независимая проверка: 435 catalog records, 434 существующих файла повторно прочитаны и сверены по bytes/SHA-256; множества GLB namespace совпали с 33 строками inventory; все 33 GLB metadata namespace ожидаемые. Все 15 concept prompts найдены. Проверка завершена без новых renders или модельных процессов; факт выполнения записан в `verification` JSON.

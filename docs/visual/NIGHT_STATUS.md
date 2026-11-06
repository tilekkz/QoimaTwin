# Состояние visual frontend v2

Дата обновления: 07.11.2026. Рабочая копия: `new-chat/work/QoimaTwin`, ветка `codex/twin-environment`. Визуальная реализация существует; итоговая приёмка ночной поставки фиксируется отдельными свидетельствами ниже.

## Реализовано

| Часть | Текущее состояние |
|---|---|
| Масштаб | Полная сцена 72×48 м: 288 стеллажей, 864 адреса, 600 занятых начальных партий, 179 операционных conveyor cells |
| Люди | Все 24 сотрудника: 12 комплектовщиков, 6 упаковщиков, 2 приёмщика, 2 отгрузчика, 2 водителя внутри двух погрузчиков |
| Модели | 21 семейство, индивидуальные Blender/GLB и четыре ракурса; отдельные master и calibration дают 23 записи в manifest |
| Сборка | Редактируемый большой master, instancing/LOD, 19 открытых узлов линии, пассивные transfer counters у упаковки |
| Viewer | Vue 3 + plain Three.js, один viewport; обзор/сверху/зоны, миникарта, выбор адреса, follow actor/order, отдельные модели и галерея референсов |
| Replay | Абсолютное время, play/pause/reset/seek, 1×/10×/30×/60×, состояния людей/грузов, attachment, остановка ленты и небольшие событийные эффекты |
| Позы | Именованные rigid joints, работа с тележкой, низкий PICK, HANDOFF/PACK/SCAN, размещение на паллете, посадка водителей и подъём вил |
| Звук | Оригинальный процедурный WebAudio: начальный mute, явный unlock, громкость/категории, ограничение четырёх voices включая loop |
| Адаптер | Загрузка совместимого inline Run v2; неизвестные размещения грузов скрываются с предупреждением |

Матовые объёмные промышленные миниатюры используют charcoal/teal steel, тёплый картон/дерево и сдержанные saffron safety accents. V1 сохранён отдельно; основная сцена собирается модулями v2, а не растяжением старого master 20×18 м.

Финальные исправления включают цельный жилет без пересечения рубашкой, связанный плечевой скат, контакты рук с грузами и рабочим коробом, пустую исходную OUT-паллету как видимый ресурс, безопасные визуальные service-точки рядом с паллетами, непрерывный поворот тележки и signed wheel roll при заднем ходе. Shared contracts и операционные graph/cell-сети сохранены. Времена ручных service connectors следуют визуальной фикстуре; плавный yaw не меняет траекторию или длительность WALK.

## Источник данных и граница готовности

Начальный режим — **VISUAL DEMO / synthetic**: один сценарий длительностью 500 секунд в полной геометрии. Он показывает tote → parcel → pallet → dispatch, независимую приёмку и короткую явно сценарную блокировку линии. Ручные service connectors и пассивные столики не создают новые shared graph edges или conveyor cells. Карточка адреса показывает исходную партию/количество, а не текущий ledger.

Арман развивает расчётное ядро отдельно: в remote-ветке `arman/backend-core`, HEAD `5a0be9d`, есть one-order engine и работа со snapshots/chunks; CLI пока сосредоточен на validate/materialize, Run exporter — следующий этап. Эта ветка не объединена с viewer. Exporter/API, массовый поток и совместимость полной интеграции ещё не приняты. Прогноз/планировщик для 200 SKU, текущий ledger, операционные KPI, A/B и streaming не подключены. Shared contracts остаются 2.0; предложение 2.1 не применялось. Подробности — [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md).

Импорт inline JSON — подготовленная граница подключения. Offered load 240/600 заказов/ч не выдаётся за достигнутый выпуск. Исследовательский прогноз v1 сохраняется отдельно от нового сценария.

Подробности: [MOTION_AND_INTEGRATION.md](MOTION_AND_INTEGRATION.md), [frontend replay API](../../frontend/src/replay/README.md), [контракты](../../contracts/README.md).

## Где лежит результат

- [Manifest](../../assets/v2/asset-manifest.json): семейства, исходники, экспортированные узлы и hashes.
- `assets/v2/blender/` — редактируемые исходники; `frontend/public/models/v2/` — runtime GLB.
- `assets/v2/previews/<asset>/{front,side,rear,three-quarter}.png` — отдельные ракурсы.
- [MODEL_QA.md](MODEL_QA.md), [BROWSER_MODEL_REVIEW.md](BROWSER_MODEL_REVIEW.md) и [personnel QA](../../assets/references/v2/personnel-QA.md) — сравнение с референсами и проверка контактов.
- [SOURCES_AND_RIGHTS.md](SOURCES_AND_RIGHTS.md) — происхождение материалов и звука.

Запуск из исходников описан в [README](../../README.md): `npm ci`, `npm run dev`, `npm run build` из `frontend/`. Для итогового пакета root укажет проверенный `START_VIEWER.ps1` и путь поставки в его `README_MORNING.md`.

## Финальные свидетельства

После финальной поправки камеры regression: **30/30 за 31,8 с**, включая 16 pure replay/audio и 14 browser cases. Независимая проверка охватила 23/23 экспортов; Khronos validation — 33/33 GLB с 0 errors и 0 warnings. Отчёты синхронизированы с `index-CwwCEUPq` / `largeWarehouse-SItJUNRu`.

Повторный performance checkpoint от 06.11.2026 22:29:17 UTC: Headless Chrome 156, ANGLE Intel UHD/D3D11, 1366×768, Low, DPR 1, replay 10×, mute; rAF-окна 60,0012 с и 60,0034 с без параллельного Blender renderer. Замер выполнен после финальной поправки камеры.

| Окно | Median FPS | Mean FPS | p95 frame | Max calls | Max triangles |
|---|---:|---:|---:|---:|---:|
| Overview | 142,86 | 100,83 | 14 мс | 154 | 270 248 |
| Follow P01 / hero | 140,85 | 99,38 | 14 мс | 191 | 418 632 |

Hero-просмотр превышает мягкие ориентиры 180 calls / 350k triangles. Это записанное ограничение визуального бюджета, несмотря на измеренный frame rate. Замер не переносится автоматически на другие устройства и не является operational throughput.

| Этап | Свидетельство |
|---|---|
| Frontend regression | [BROWSER_QA.json](BROWSER_QA.json) |
| GLB и канонические входы | [GLB_VALIDATION.json](GLB_VALIDATION.json), [canonical-spec-checks.json](../../assets/v2/canonical-spec-checks.json) |
| Два 60-секундных измерения на устройстве | [PERFORMANCE.json](PERFORMANCE.json) |
| Реальная запись viewer и контрольный кадр | Source: `work/night-video/QoimaTwin_Night_Demo.mp4`, `work/night-video/poster.png`; финальные медиа и `README_MORNING.md` — в корне готового пакета |
| Сводные ограничения и приёмка | [FINAL_REVIEW.md](FINAL_REVIEW.md) |

Финальное демо снято из viewer после camera fix:89,966667с,1366×768,30fps,H.264/yuv420p. Пять отдельных клипов показывают PICK,HANDOFF,PACK,forklift load и SCAN на1×. Просмотрены пять кадров основного MP4 и контроль упаковки; ошибочная окклюзия погрузчиков закрыта. Запись muted, без аудиодорожки; SFX включаются пользователем в viewer. Точные длительности, hashes и metadata — [MEDIA_QA.json](MEDIA_QA.json).

Запуск из готовой папки проверен реальной командой `powershell -NoProfile -ExecutionPolicy Bypass -File .\START_VIEWER.ps1`:localhost4180,58 файлов viewer побайтно совпадают с проверенным production build,24 человека/288 стеллажей/864 адреса/179 cells, стенд водителя и follow погрузчика открываются, ошибок страницы и внешних API/CDN requests нет. Свидетельство — [PACKAGE_LAUNCH_QA.json](PACKAGE_LAUNCH_QA.json).

Поставка: `outputs/QoimaTwin_Night_Final`, соседний ZIP и SHA256. Исходный commit и фактический статус публикации в origin записываются упаковщиком в корневые `README_MORNING.md` и `DELIVERY_MANIFEST.json`; они не выводятся из промежуточного HEAD.

## Контекст проверки исходников

Tier 2, graph project `qoima-twin`; последний подтверждённый ответ coverage — generation `2026-11-06T22:22:36Z`. Проверенные пути исходников/документов/отчётов имеют `no_recorded_issue` с freshness `metadata_changed`; `gltf-final.log` исключён gitignore. Выполнено прямое чтение релевантных файлов, включая этот log. Это best-effort сигнал, а не полный аудит. Автор этого обновления не запускал index/memory refresh.

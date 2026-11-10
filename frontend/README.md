# QoimaTwin visual frontend

Vue3 + TypeScript + Vite + Three.js. Основной экран — склад72×48м:
288 стеллажей,864 адреса,600 начальных партий,24 сотрудника,2 погрузчика,
6 упаковочных постов и179 логических ячеек конвейера. Один renderer,
instancing/LOD и21 отдельный стенд моделей с четырьмя ракурсами.

Начальный режим **VISUAL DEMO / synthetic** воспроизводит500-секундную
согласованную визуальную фикстуру. Есть play/pause/reset/seek, выбор объектов,
следование сотруднику/заказу, обзор/вид сверху, локальные референсы,
low/high, reduced motion и оригинальные процедурные SFX с начальным mute.
Импорт inline Run2.0 подготовлен; расчёты, бизнес-snapshots, API streaming
и A/B ещё не подключены к viewer. Геометрия и скорость картинки не являются
доказательством пропускной способности или экономии.

## Запуск из исходников

Node22.12+, проверены Node24.19/npm11.17. Из этой папки:

```powershell
npm ci
npm run dev
```

Открыть http://127.0.0.1:5173. Production:

```powershell
npm run build
npm run preview
```

Открыть http://127.0.0.1:4173. Все модели/референсы загружаются локально;
для готового viewer API/CDN не требуются. `/api` в dev имеет настраиваемый
proxy из `.env.example`; наличие proxy не означает подключённый backend.

## Проверки и калибровка

```powershell
npm run typecheck
npm run verify:assets
npm run test:smoke
```

Smoke использует установленный Google Chrome и сам запускает production
preview. Для уже запущенного static viewer можно задать
`$env:QOIMA_TEST_BASE_URL='http://127.0.0.1:4180'`.
Pure replay/audio отдельно: `npx playwright test --config src/replay/replay-core.config.ts`.
Его outputDir изолирован от browser PNG. Полный regression содержит30 проверок.

`?calibration=v2` проверяет реальные оси/anchors/размеры GLB v2;
`?calibration=1` сохраняет старый технический стенд. Старые ассеты не
растягиваются в большой склад. Редактируемые v2 модели находятся в
`../assets/v2/blender/`, runtime — `public/models/v2/`.

## Передача и свидетельства

- [Replay API](src/replay/README.md) и [интеграция](../docs/visual/MOTION_AND_INTEGRATION.md).
- [Текущий backend handoff](../docs/visual/BACKEND_HANDOFF.md): reviewed SHA,2.0/2.1 и границы exporter/snapshot/chunk.
- [Browser QA](../docs/visual/BROWSER_QA.json), [модели](../docs/visual/MODEL_QA.md), [performance](../docs/visual/PERFORMANCE.md).
- [Источники и права](../docs/visual/SOURCES_AND_RIGHTS.md). Донорские декоративные KPI/AGV/GLB не используются.

Скрипты записи в `tools/` снимают настоящий viewer. Для них дополнительно
нужен `npx playwright install ffmpeg`; MP4 кодируется через
`../tools/visual/finalize_media.py --ffmpeg <путь-к-ffmpeg>`.
Three/GLTFLoader создают ленивый chunk около583kB; фактический FPS измерен
отдельно и не выводится из размера JS или успешной сборки.

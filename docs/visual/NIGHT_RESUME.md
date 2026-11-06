# Checkpoint visual v2 — ночная поставка завершена

Рабочая копия: `C:/Users/izbas/Documents/Codex/2026-11-06/new-chat/work/QoimaTwin`.
Ветка: `codex/twin-environment`. Состояние и границы: [NIGHT_STATUS.md](NIGHT_STATUS.md).
Финальный исходный SHA и remote status берутся из `README_MORNING.md` /
`DELIVERY_MANIFEST.json` в корне пакета, а не из старого checkpoint HEAD.

## Что открывать

Готовая папка: `C:/Users/izbas/Documents/Codex/2026-11-06/new-chat/outputs/QoimaTwin_Night_Final`.
В ней `start-viewer.cmd` или команда:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\START_VIEWER.ps1
```

Адрес http://127.0.0.1:4180. Нужен Node 22.12+; npm install/API/CDN для
готового viewer не нужны. Сервер оставить открытым, Ctrl+C завершает его.
MP4, poster, пять action clips,visual-review.html,исходники/GLB и QA лежат в пакете.
ZIP находится рядом; SHA256 и CRC проверяет упаковщик.

## Закрытые проверки

- Production build/vue-tsc и 30/30 regression: 16 core + 14 browser, 31.805 с.
- 23/23 v2 GLB независимо декодированы; Khronos33/33 с 0 errors / 0 warnings.
- 21 семейство:84 Blender-ракурса с reference/render,84 browser views,
  manifest/model hashes совпадают. Персонал и контакты переработаны.
- Full 72×48,288 racks/864 slots/600 lots/200 SKU,24 actors с двумя водителями,
  2 forklifts/6 pack stations/179 cells/19 junctions.
- Два 60-секундных Low-окна на Intel UHD:median142.86/140.85FPS,p95=14ms.
  Hero peak191calls/418632tri превышает мягкий бюджет, это раскрыто в отчёте.
- Настоящее демо89.966667с и5 клипов проверены ffprobe и по контрольным кадрам;
  muted capture,1366×768/30fps/H.264. Событийный звук доступен в viewer.
- Реальный запуск готового `START_VIEWER.ps1`:58 viewer-файлов идентичны
  production,stand/follow работают,0 page errors и0 внешних requests.

Свидетельства: [BROWSER_QA.json](BROWSER_QA.json),[MODEL_QA.md](MODEL_QA.md),
[FINAL_REVIEW.md](FINAL_REVIEW.md),[PERFORMANCE.json](PERFORMANCE.json),
[MEDIA_QA.json](MEDIA_QA.json),[PACKAGE_LAUNCH_QA.json](PACKAGE_LAUNCH_QA.json).

## Граница следующей интеграции

Начальный режим **VISUAL DEMO / synthetic**: согласованный500-секундный
визуальный сценарий в полном складе, без выдуманных KPI/экономии. Карточки
мест показывают исходный остаток. Это не текущий inventory ledger.

В просмотренной `origin/arman/backend-core` на `5a0be9d` уже существуют
one-order engine,recorder,settled snapshots иhalf-open chunks. Ветка не
объединена с visual checkout; Run exporter/API ещё не подключены. Общий
wire-contract остаётся2.0;2.1 — предложение. Следующий шаг — согласовать
exported seq/cursors,typed snapshot state иcargo placements,получить настоящий
Run и подключать bounded chunks/seek по backend state. Подробно:
[BACKEND_HANDOFF.md](BACKEND_HANDOFF.md),[MOTION_AND_INTEGRATION.md](MOTION_AND_INTEGRATION.md).
Массовый поток240/600,forecast/planner,ledger/API/KPI/A/B принадлежат Арману.

## Как безопасно продолжать

Геометрия заморожена; повторный экспорт/рендер нужен при конкретном дефекте.
Исходники `assets/v2/blender`,builders `tools/blender/v2`,runtime `frontend`.
Ночной исходный brief сохранён вне git в соседнем `../overnight-brief/`.
Shared contracts,data/probes и original verification_report.json сохранены.
Pure config имеет отдельный `work/replay-core-test-results`; полный Playwright
очищает `frontend/test-results`,поэтому сохраняйте QA evidence перед новым run.

Для разработки из frontend:`npm ci`,`npm run dev`;production:`npm run build`.
Процессы/headless contexts после записи закрыты; актуальность оставленного
сервера проверяйте по порту. Не запускайте второй renderer во время performance.
Graph Tier2,generation22:22:36UTC,0 skipped/parse-partial;Windows freshness
metadata_changed дополнен прямым чтением исходников. [SOURCE_COVERAGE.json](SOURCE_COVERAGE.json)
фиксирует ограничения. Obsidian memory refresh не выполнялся: его ведёт daily run.

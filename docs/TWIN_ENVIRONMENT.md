# Проверка окружения Qoyma Twin

Дата: 06.11.2026. Исходный commit `ea35edf`, локальная ветка
`codex/twin-environment`. Изучены все 6 основных документов, README, glossary,
лицензионные заметки, контракты, manifest/результаты и исследовательские Python
скрипты. PDF извлечён для проверки дублирующего материала; каноничны Markdown
ТЗ и contracts. Исходные 43 файла сверены с package_manifest до изменений.

## Что подготовлено

- Отдельный frontend Vue/Three с закреплёнными зависимостями и localhost-only Vite.
- Прямой импорт общей геометрии/ручного Run, без копирования ID в отдельный набор.
- Ленивая загрузка Three/GLTFLoader, освобождение renderer/controls/geometry/material,
  resize и понятная ошибка загрузки модели.
- Технический Blender source/GLB с метром, осями и anchor реальной ячейки.
- Khronos glTF Validator, Chrome/Playwright smoke tests и Python-проверка входов.
- Изолированный `.venv` только для validation tools; requirements с transitive lock.
- Скрипты запуска клиента, Blender и воспроизводимого экспорта.
- API proxy на localhost:8000; граница интеграции описана в TWIN_INTEGRATION.md.

## Проверенные версии

| Инструмент | Версия |
|---|---|
| Node / npm | 24.19.0 / 11.17.0 |
| Python validation venv | 3.12.10 |
| Blender | 5.0.1 |
| Vue / Three | 3.5.45 / 0.169.0 (r169) |
| Vite / plugin-vue | 8.3.6 / 6.0.10 |
| TypeScript / vue-tsc | 5.9.3 / 3.3.14 |
| Playwright | 1.65.0 |
| gltf-validator | 2.0.0-dev.3.10 |
| jsonschema | 4.26.0 |

## Фактические проверки

- Донор: npm ci из приложенного lockfile и vue-tsc/vite production build прошли.
  Его зависимости дали 5 npm audit findings (1 high, 4 moderate). Донор оставлен
  в work только как референс; его исходный Vite dev server не запущен.
- Рабочий frontend: typecheck и production build прошли. npm audit: 0 findings
  на дату проверки. Lockfile сохранён; lifecycle scripts при установке отключены.
  Повторный npm ci --offline по этому lockfile также прошёл.
- Python: 113 проверок контрактов/графа/ручных чисел/данных прошли; pip check чист.
  Проверены 20 SKU, 31/33 граф, 21.2м, тайминги, законные WALK, выполнимость
  transfers, 1745 visits/749 корзин, 400 целей прогноза и отсутствие raw IDs.
- Исходные документы, контракты и data/probe результаты не изменены. Из snapshot
  намеренно дополнен только .gitignore; в исходном package_manifest новые файлы
  не добавлялись, чтобы сохранить исследовательскую контрольную сумму.
- Blender background export завершился; calibration.glb 2548 bytes; Khronos:
  0 errors, 0 warnings, 1 info (неиспользуемый TEXCOORD_0, текстур у куба нет).
- 2 smoke tests прошли в реальном Chrome: production/WebGL/локальный GLB,
  метр/оси/anchor, resize и отсутствие внешних сетевых запросов; 404 GLB даёт
  явное error state. Это не тест производительности готового склада.
- Dev server также проверен через browser tools: Chrome156, один canvas,
  WebGL через ANGLE/Intel UHD Graphics/D3D11, статус ready. Это подтверждает
  реальное отображение стенда на текущей GPU, не целевой FPS будущего twin.
- Live Blender MCP отвечает: protocol13 совпадает, addon1.8 актуален;
  прочитаны 6 объектов task calibration.blend. Внешние asset/generation providers
  отключены. Background export процесс закрыт; отдельный task Blender оставлен
  для дальнейшей работы.

## Граф кода

Проект `qoima-twin` проиндексирован. После закрытия MCP transport использован
работающий установленный CLI0.10.8, без изменения настроек Codex. Индекс
обновлён до 1312 nodes/1534 edges, generation 2026-11-06T18:34:51Z.
Проверено покрытие 34 точных путей и областей frontend/src, tools: recorded
parse gaps отсутствуют, но CLI пометил freshness как metadata_changed/not_tracked
даже после индексации. Поэтому выводы опираются также на прямое чтение исходников
и реальные проверки. Это ограничение метаданных графа, а не утверждение о полном
структурном аудите. Для следующей работы доступен CLI; chat MCP transport может
потребовать нового подключения в следующем сеансе.

## Воспроизведение

Из корня репозитория:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-twin-tools.lock.txt
.\.venv\Scripts\python.exe tools/verify_preparation.py
powershell -NoProfile -ExecutionPolicy Bypass -File tools/export-calibration.ps1
cd frontend
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd run build
npm.cmd run verify:assets
npm.cmd run test:smoke
npm.cmd run dev
```

В Codex sandbox локальные TCP-соединения/браузер и установка пакетов могут
потребовать tool escalation; из обычного терминала это стандартные команды.
Не менять глобальные Node/Python или пользовательские Blender preferences.

## Граница готовности

Подготовка участка A завершена. Готового склада, replay, расчётного API и 60s
performance test ещё нет. Backend/ML окружение участника B не изменялось;
исходный XLSX не загружался повторно, модели не переобучались. Его исходный
requirements-probe.txt описывает прежние исследования; не устанавливать его
в validation venv участника A ради frontend.

Предупреждение сборки о Three chunk >500kB известно (ленивый chunk ~577kB,
146kB gzip). FPS и бюджет draw calls следует измерять на готовой модели.
Новый код и модели подготовлены локально; push в GitHub не выполнялся.

Для графового CLI при недоступности MCP, например:

```powershell
& 'C:\Users\izbas\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe' cli --json index_status --project qoima-twin
```

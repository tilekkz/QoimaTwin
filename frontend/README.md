# Клиент участника A

Подготовлен технический стенд: Vue 3 + TypeScript + Vite + Three.js,
GLTFLoader/OrbitControls, локальный calibration.glb и прямой импорт общих
контрактов. Это проверка окружения перед 3D-дизайном, не реализация склада/replay.

Из корня репозитория в PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-client.ps1
```

Адрес: http://127.0.0.1:5173. Установка с нуля:

```powershell
cd frontend
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd run build
npm.cmd run verify:assets
npm.cmd run test:smoke
```

Нужны Node >=22.12 и установленный Google Chrome для smoke tests. На этой
машине проверены Node 24.19.0 / npm 11.17.0. Chrome не загружается тестом.
Все runtime-ресурсы локальные. Для проверки production: `npm.cmd run preview`,
http://127.0.0.1:4173. Smoke test сам запускает и закрывает этот preview.

`/api` в dev проксируется на http://127.0.0.1:8000; адрес меняется в локальном
`.env` по примеру `.env.example`. Реального backend пока нет. Стенд не посылает
фиктивные API-запросы и не выдаёт ручную фикстуру за результат UCI.

## Ответственность

- `src/app`: экран, панели и состояния запроса (A).
- `src/scene`: Three.js, модели, registry, камеры, выбор объектов (A).
- `src/replay`: часы и восстановление состояния (A; реализация впереди).
- `src/contracts`: прямое чтение канонических файлов из корня (общая граница).
- `public/models`: runtime GLB; исходники Blender в `assets/blender` (A).

Следующий шаг: graybox по layout.example.json и проигрывание
hand_checked_run.json; затем собственные rack/crate/picker/pack assets.
Один renderer, два scissor viewport, общий clock/camera; резерв — A/B toggle.

Донор Xxcool/smart-warehouse сохранён в исходном ZIP и распакован только в
игнорируемом `work/donor-reference`. Его исходная сборка воспроизведена; его
декоративные KPI, циклы AGV и большие GLB не скопированы в рабочий клиент.
Three r169 оставлен совместимым с донором. Инструменты сборки обновлены после
проверки npm audit; фактические версии зафиксированы package-lock.json.

Vite сообщает о крупном ленивом Three/GLTFLoader chunk (~577 kB / 146 kB gzip).
Сейчас это известная характеристика стенда; бюджет сцены и FPS проверяются
после появления склада, а не выводятся из успешной сборки.

# Репозитории и исследование Qoyma Twin

Проверено 06.11.2026. Разделяем уровни уверенности: «собран локально», «прочитаны конкретные исходники/лицензия», «референс с ограничениями». README и красивое видео сами по себе не доказывают наличие планировщика или симуляции.

## Основной набор для двух дней

| Репозиторий / библиотека | Что взять | Лицензия и проверка | Решение |
|---|---|---|---|
| [Xxcool/smart-warehouse](https://github.com/Xxcool/smart-warehouse) | Vue/Three оболочка, GLTFLoader, OrbitControls, raycast, прототип popover; GLB как визуальный референс/источник повторных деталей | MIT-файл прочитан; commit ea8c968515a4fc19be26aaf1a3f9419aec159438; install и production build успешно выполнены | Основной визуальный донор |
| [SimPy](https://gitlab.com/team-simpy/simpy) | Environment, timeout, Store, последовательные процессы двух работников и упаковки | MIT; [официальная документация ресурсов](https://simpy.readthedocs.io/en/latest/topical_guides/resources.html) и пример процессов | Основная библиотека симуляции |
| [TerexSpace/whse-optimize-toolkit](https://github.com/TerexSpace/whse-optimize-toolkit) | Типы данных/CSV-адаптер и идея ABC из небольших файлов | MIT прочитана; bounded source audit, целый проект не запускался | Точечный донор, не основа всего backend |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | Pipeline, OneHotEncoder, HistGradientBoostingRegressor | BSD-3-Clause; локальный CPU forecast probe выполнен | Основной ML, готовые прогнозы приложены |
| [Nixtla/mlforecast](https://github.com/Nixtla/mlforecast) | Формат panel, лаги, временная cross-validation | Apache-2.0, LICENSE/pyproject прочитаны; не запускался | Резерв, если команда уже знакома; для20SKU не нужен дополнительный стек |
| [google/or-tools](https://github.com/google/or-tools) | CP-SAT назначение с ограничениями | Apache-2.0; официальный assignment sample проверен | Расширение после MVP, без него проще |
| [donmccurdy/glTF-Transform](https://github.com/donmccurdy/glTF-Transform) | Проверка/оптимизация GLB при необходимости | MIT согласно репозиторию; в этом исследовании не запускался | Инструмент Тилека, после проверки IDs после оптимизации |

Рекомендуемая композиция: адаптировать небольшой визуальный слой Xxcool, свою модель склада написать поверх SimPy, прогноз — plain sklearn, ограниченные обмены — короткий собственный перебор. Попытка скрестить несколько целых WMS/robotics-приложений увеличивает работу.

## Xxcool: что реально подтверждено

Локально выполнено `npm install --ignore-scripts --no-audit --no-fund` и `npm run build` в изолированной проверочной копии. `vue-tsc && vite build` прошли; Vite 5.4.21 собрал 35 модулей. JS Three chunk около527.6 kB без gzip/134.4 kB gzip. Проверка сборки не является проверкой FPS, памяти или всех кликов в браузере.

Исходники:

- [`src/core/WarehouseScene.ts`](https://github.com/Xxcool/smart-warehouse/blob/ea8c968515a4fc19be26aaf1a3f9419aec159438/src/core/WarehouseScene.ts): загрузчик GLB около624 строки; камера/controls в начале; raycast/popup; animate около1501 строки. Движение AGV задаётся фазой `(accumulatedTime × 0.035 + offset) % 1`, груз меняется по интервалам этой фазы. Это визуальная логика цикла, не исполнение наших заказов.
- [`src/core/constants.ts`](https://github.com/Xxcool/smart-warehouse/blob/ea8c968515a4fc19be26aaf1a3f9419aec159438/src/core/constants.ts): декоративные значения оборудования/температуры/нагрузки. Их удалить, заменить данными собственного run.
- [`src/components/LeftTelemetryHud.vue`](https://github.com/Xxcool/smart-warehouse/blob/ea8c968515a4fc19be26aaf1a3f9419aec159438/src/components/LeftTelemetryHud.vue): исходные KPI в шаблоне заданы числами. Не переименовывать их в наши «достигнутые показатели».
- [`src/App.vue`](https://github.com/Xxcool/smart-warehouse/blob/ea8c968515a4fc19be26aaf1a3f9419aec159438/src/App.vue): точки подключения HUD/scene/loading/выбора. Использовать как основу интеграции, убрать нерелевантные экраны.

Фактический `public/smart_warehouse.glb`: 4,039,312 байт, 831 node, 825 meshes, 886 primitives, примерно59,790 индексированных треугольников, 42 материала, встроенных textures нет. В `public/models` лежит копия того же размера. Это собственный разбор JSON-chunk GLB, не измерение draw calls в работающей сцене. Большое число мешей и physical/transmission материалов может быть дороже числа полигонов.

Не переносить целиком заводской двор с грузовиками/холодильником/роборуками в наш маленький склад. Быстрее взять viewer и повторяемые элементы, а 20×18м сцену сделать модульно по общей геометрии. Исходный автор заявляет Blender-пайплайн, но в проверенном дереве готовый `.blend` не подтверждён: способность открыть GLB в Blender не равна наличию редактируемого авторского проекта.

В пакет включён чистый source archive выбранного commit с MIT; node_modules/dist не включены. Код/GLB находятся под общей лицензией репозитория, отдельный документ цепочки происхождения ассетов не обнаружен в проверенном наборе. Для конкурсного оригинального вида разумно сделать свои простые модели и сохранить атрибуцию реально перенесённых частей.

## TerexSpace: полезные части и ловушки

Проверенные файлы: [heuristics.py](https://github.com/TerexSpace/whse-optimize-toolkit/blob/main/src/wms_optlab/slotting/heuristics.py), [milp_models.py](https://github.com/TerexSpace/whse-optimize-toolkit/blob/main/src/wms_optlab/slotting/milp_models.py), [topology.py](https://github.com/TerexSpace/whse-optimize-toolkit/blob/main/src/wms_optlab/layout/topology.py), [adapters_erp.py](https://github.com/TerexSpace/whse-optimize-toolkit/blob/main/src/wms_optlab/data/adapters_erp.py).

ABC суммирует quantities. Для Qoyma заменить на unique invoice-SKU visits. Capacity в прочитанной MILP-части помечена TODO, поэтому название функции не доказывает учёт вместимости. Без explicit aisle_connectivity topology создаёт fully connected Manhattan graph: на нашем складе такие связи могут проходить через стеллажи. Передавать только явные разрешённые связи. Бюджет2 swaps и выполнимые transfer через буфер реализуются отдельно.

Не переносить ERP/MILP-зависимости ради функции сортировки из нескольких строк. Если заимствование не экономит время интеграции, написать эквивалентную собственную предметную функцию по ТЗ и оставить репозиторий исследовательским референсом.

## Дополнительные репозитории: прочитано, но в MVP не брать

| Репозиторий | Подтверждённое содержание | Почему не брать целиком |
|---|---|---|
| [semitable/robotic-warehouse](https://github.com/semitable/robotic-warehouse) | MIT, `rware/warehouse.py`: роботы поднимают целые shelves, действия движения/load, requested shelves и конфликты | Goods-to-person и RL environment; это другой операционный процесс |
| [Vikas-Jakhar/warehouse-operations-optimization](https://github.com/Vikas-Jakhar/warehouse-operations-optimization) | `src/simulation.py`: сравнение mapping по batches, distance/speed + operations | Нет очереди2pickers+packing; названная S-shape считает возврат по каждому aisle; Manhattan shortcut. Отдельный LICENSE не подтверждён |
| [ashrafelgaaly/AI-SmartWarehouseRoute](https://github.com/ashrafelgaaly/AI-SmartWarehouseRoute) | `OrderPickingSimulation.py`: короткий SimPy worker pool и времена отбора | Случайные координаты, нет нашего графа/pack; возвращение к pack не обеспечено; лицензия не подтверждена |
| [danielbfogel-lgtm/retail-demand-forecasting](https://github.com/danielbfogel-lgtm/retail-demand-forecasting) | MIT code; `src/pipeline/features.py`, `cleaning.py`: shifted rolling, разделение returns | Месячная задача и большой workflow; взять идеи проверки leakage, не переносить монолит |
| [virbahu/warehouse-slotting-optimizer](https://github.com/virbahu/warehouse-slotting-optimizer) | Небольшая сортировка popularity/близости | Нет полноценного relocation/маршрутов; LICENSE содержит только заголовок MIT/copyright без полного grant — статус не считать решённым |

WOSO и другие проекты с одним обещающим README не включены как проверенная основа. Не использовать чужие demo-проценты улучшения как ориентир нашего результата. Для репозиториев с неясной лицензией обсуждать общую идею допустимо, копировать код в поставку пока не нужно.

## Что уже существует на рынке

[Lucas Systems Dynamic Slotting](https://www.lucasware.com/slotting/) описывает прогнозные данные, небольшие изменения размещения и what-if. [Вводный материал](https://www.lucasware.com/knowledge-center/introduction-to-dynamic-slotting/) включает режим ограниченного числа swap. Поэтому связка «forecast → несколько обменов → симуляция» уже существует.

[Grid Dynamics Intralogistics Optimization Starter Kit](https://www.griddynamics.com/solutions/intralogistics-optimization-starter-kit) использует данные размещения/заказов и twin для оптимизации внутрискладских процессов. [SSI SCHAEFER](https://www.ssi-schaefer.com/en-asia/newsroom/company-blog/the-digital-warehouse-part-2-4-1456312) также описывает складские двойники. Это подтверждает прикладной класс задачи, но не наличие спроса на наш конкретный продукт.

Научный пример: [Zhang, 2026, warehouse order picking and DT-aligned simulation](https://link.springer.com/article/10.1007/s42452-026-08990-7). Полезна сама структура эксперимента/ablation; их проценты не относятся к нашим данным и методам. Тяжёлый genetic algorithm не обязателен для20SKU.

Позиционирование прототипа: понятный CSV-вход, малая модель участка, прозрачные ограничения, честная стоимость переносов, наглядная проверка. Локализация/низкая стоимость/удобство — гипотезы, которые нужно подтвердить пилотом. Не обещать первое место или технологическое первенство.

## Лицензии и собственный вклад

Для каждого перенесённого файла сохранить URL, commit, лицензию и заметку об изменениях. Включить MIT/BSD copyright notices и Apache NOTICE при применимости. Данные UCI имеют самостоятельную CC BY4.0 атрибуцию.

Наш вклад: целевая переменная посещений, temporal evaluation, ограниченный план с физическими transfer, проходимый граф, SimPy-процесс людей/упаковки, единый eventlog, корректное сравнение и сценарии. 3D-донор сам этого не обеспечивает. Набор лицензий в документах — исходная информация; финальный THIRD_PARTY_NOTICES должен перечислять именно реально использованные зависимости/файлы.

# Контракт данных v1

Это стартовый контракт для независимой работы Тилека и Армана, а не готовый сервер. `layout.example.json` — полноценная выбранная геометрия. `hand_checked_run.json` — искусственная однозаказная фикстура с ручными ожидаемыми числами, не результат на UCI. Существующие UCI CSV находятся в соседней папке data.

## Общие правила

- UTF-8 JSON, `schema_version="1.0"`, длина в метрах, время в секундах от начала прогона, координаты `[x,y,z]`, Y вверх.
- Все ID строки. SKU, slot, node и actor — разные пространства идентификаторов. Нельзя отправить sku_id вместо slot_id.
- `layout_version="qoyma-20x18-v1"`; одно размещение не меняет geometry. Ключи assignment — slot_id, значения — sku_id, каждый SKU/slot встречается один раз.
- Полный начальный assignment содержит ровно двадцать позиций. BUFFER не является21-й торговой ячейкой и в assignment отсутствует.
- Точность float сохраняется в JSON, UI округляет отображение. Нет отрицательных длительностей, NaN и Infinity.
- Тестовая фикстура содержит SAMPLE_01…SAMPLE_20: это специально искусственные SKU, не реальные артикулы. Рабочий catalog использует sku_master_20.csv.

## Сущности

`Layout`: units, bounds, nodes, edges, slots, pack_node_id, buffer_node_id. `nodes` содержат pos, `edges` — a/b/length_m и трактуются неориентированными. `slots` содержат pick_node_id, bin_anchor, rack_center, rack_size. Источник данных о проходимости — edges, не положение коробки.

`Scenario`: scenario_id, provenance, orders. Order содержит order_id, arrival_s и lines `{sku_id,quantity}`. Строки уже объединены до уникального SKU в заказе. Любая случайность должна быть материализована до запуска двух прогонов; одинакового seed недостаточно.

`Forecast`: forecast_id, prediction_date, trained_before, data_version, model_id, predictions `[{sku_id,expected_visits}]`, backtest summary. prediction_date строго позже доступной истории. Значения спроса могут быть дробными.

`Plan`: plan_id, source_assignment_id, forecast_id, max_swaps, assignment_after, swaps, transfers, relocation_labor_s, surrogate_before_s, surrogate_after_including_relocation_s. Поле transfers показывает физическую выполнимость, а не только красивую стрелку обмена.

`Comparison`: comparison_id, scenario_id, layout_version, config, baseline_run и candidate_run. Оба ссылаются на один orders_hash и операции; изменяется только assignment. Расхождение staffing/routes/arrival rules делает comparison невалидным.

## Run и replay

Структура `Run` зафиксирована в run.schema.json. Она содержит initial_assignment, actors, scenario, config, actions, events, orders_summary и metrics. `actors` задаёт стабильные ID, role и initial_pos; отсутствие действия у свободного P2 не означает отсутствие второго работника. Он остаётся в initial_pos до своего первого действия.

`actions`: интервалы `{action_id,actor_id,kind,start_s,end_s,order_id,...}`. WALK содержит waypoints `{node_id,pos,at_s}`: первая/последняя точки совпадают со start/end. PICK/DROPOFF/IDLE/PACK содержат pos; PICK дополнительно sku_id/slot_id. Разные действия одного actor не перекрываются. Фронтенд не интерполирует движение между разными WALK через промежуточный PICK.

`events`: мгновенные факты `{seq,at_s,kind,order_id,actor_id?}`. Порядок `(at_s,seq)`. В минимуме order_arrived, order_assigned, sku_picked, picked_last, pick_finished, pack_started, order_completed. `pick_finished` — корзина сдана после возврата и dropoff, worker свободен. `picked_last` — последний товар взят, возврат ещё может продолжаться.

Событие применяется при `at_s <= replay_time`; интервалы `[start_s,end_s)`. При seek derived state строится заново из initial state и событий. Фронтенд вправе посчитать счётчик из событий, но сверяет финальный счётчик с metrics; не пересчитывает свой физический опыт.

Метрики — численные итоги backend, не произвольные строки: distance_m, picker_busy_s, packer_busy_s, makespan_s, mean_cycle_s, p95_cycle_s, mean_pack_wait_s, max_pack_queue, completed_total, completed_by_horizon, relocation_labor_s. Итог сравнения дополнительно содержит gross_pick_labor_saved_s и net_labor_saved_s. Для пустой выборки неопределённые mean/percentiles/ratios = null.

P95 использовать метод NumPy `quantile(...,method="linear")` или его точный эквивалент. Очередь упаковки считается без заказа в обслуживании; поступление при свободном упаковщике и немедленном начале обслуживания не создаёт положительного интервала очереди. При одинаковом timestamp сначала освобождение упаковщика, затем FIFO-dispatch; max queue измерять после dispatch. Для одного заказа без ожидания max_pack_queue=0.

`baseline_assignment.example.json` уже содержит реальное frozen ABC для выбранных20SKU в runtime-направлении slot→SKU. `plan.example.json` — пример рассчитанного плана для явно введённой акции5×; он не содержит фактическую экономию синтетического потока. `hand_checked_run.json` остаётся независимой искусственной фикстурой SAMPLE_SKU для проверки арифметики.

## Валидация поверх JSON Schema

JSON Schema проверяет форму, но сама не доказывает физический смысл. Backend обязан дополнительно проверить:

1. Уникальность IDs и взаимно однозначность assignment; все ссылки существуют.
2. Связность graph от PACK, положительные веса и совпадение веса с геометрией отрезка.
3. Каждый WALK идёт только между соседними node, а его длительность соответствует расстоянию/скорости.
4. У PICK координата совпадает с pick_node указанного slot, а assignment связывает slot с нужным SKU.
5. Arrival≤assigned≤picked_last≤pick_finished≤pack_started≤completed. Между pick_finished и pack_started допускается очередь.
6. Не более двух picker и одного packer; PACK действия одного packer не перекрываются.
7. Моментальные события и actions согласованы; финальные метрики получены из этого же run.
8. План исполним последовательными transfer в свободный адрес; buffer пуст до и после, товары не потеряны.
9. forecast cutoff и выбранные test inputs не нарушают временной причинности.

## Что передать друг другу первым

Тилек получает layout.example.json и hand_checked_run.json, делает scene + replay. Арман получает эти же файлы как acceptance fixture и экспортирует такой же формат из расчётного ядра. При необходимости изменения поля оба обновляют schema_version и README до интеграции. Эта граница позволяет не ждать финального GLB или финальной ML-модели.

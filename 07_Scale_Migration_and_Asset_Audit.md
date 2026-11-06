# Увеличение масштаба: решение и миграция

Версия 2.0, 07.11.2026. Владелец 3D/клиента — Тилек, модели операций/архитектуры — Арман.

## Причина и принятое решение

Проблема действительно заложена в ТЗ v1: 360 м², 20 SKU, 2 отборщика, 1 упаковщик, неограниченная очередь упаковки. Это контролируемый маленький опыт, из которого нельзя получить крупный живой склад одной сменой масштаба камеры.

Теперь primary profile — 3456 м², 200 SKU, 864 адреса, 24 человека и 179 conveyor cells. Увеличение площади 9.6×, ассортимента 10×, штата 8× к трём людям старой модели. Резерв, приёмка и отгрузка имеют собственные сущности. Новая версия не наследует операционные результаты v1.

## Что обнаружено в приложенном архиве

Архив QoimaTwin-3D-assets.zip проверен read-only; его инструкции не исполнялись. В нём 114 записей. Прототипы: buffer-pallet, crate, environment, forklift, ibc-tote, packing-station, picker-cart, rack-bay; есть .blend, GLB, builders, previews.

assemble_warehouse.py ожидает ровно 20 slots. Master scene содержит 20 rack и 20 crate, две static picker figures, один pack, один parked forklift и один IBC. Поза человека иллюстративна. Конвейера, операционных workers на упаковке/приёмке/отгрузке и replay нет.

GLB master: 537 nodes, 375 mesh nodes, 77 unique meshes, 77 materials; 50556 triangles по уникальной geometry, **136956 с учётом размещённых экземпляров**. Нет glTF animations/skins/textures. Отсутствие skin не мешает простому событийно управляемому rigid avatar.

В архиве есть performance-single-view.json: около 144.93 FPS/7.1 ms. Это результат старого статичного одиночного вида в его условиях, не доказательство скорости большого склада с активными сущностями. Новый runtime-performance не измерен.

## Переиспользовать и переделать

| Материал | Решение |
|---|---|
| rack-bay | Сохранить визуальный язык, выделить примитивы стоек/балок и сделать low LOD; новый модуль 5.4 м и 3 адресуемых уровня |
| crate, buffer-pallet | Использовать как прототипы, общие материалы; semantic binding к lot/cargo |
| packing-station | Шесть экземпляров по layout; pack buffers и выходная тара отдельные сущности |
| picker-cart | Прототип для 12 отборщиков; cart/avatar transform из backend |
| forklift | Два экземпляра на отдельных транспортных графах, управляемые заданиями |
| ibc-tote | Сохранить как отдельное семейство тары; не превращать все подарочные SKU в жидкость |
| environment | Заменить цельный 20×18 на модуль пола/колонн/стены/дока 72×48 |
| warehouse.glb/.blend | Оставить reference, не использовать как растянутый runtime master |

Добавить: modular conveyor straight/turn/diverter/guard, order tote, sealed parcel, pallet stack, neutral worker без cart, loading dock/door, разметку зон, LOD/proxy. Не моделировать 200 уникальных товарных изделий: SKU различаются этикеткой/цветом и данными.

## Порядок миграции без потери работ

1. Сохранить исходный ZIP/.blend неизменными, пометить layout v1. Новую сцену собирать отдельно.
2. Согласовать contracts/layout.example.json v2 и simulation_defaults.json до работы ночью.
3. Удалить из нового assembler жёсткие ожидания 20 slots/2 figures/1 pack и чтение layout v1. Считать counts из manifest; проверять их против профиля v2.
4. Сначала graybox всех 288 rack modules, 864 bin anchors, 24 actors, conveyors и dock zones. Даже без красоты должна читаться вся территория.
5. Разделить static shell, reusable asset prototypes и runtime cargo. В warehouse shell не запекать 24 статичных человека или сотни вечных коробок, дублирующих динамику.
6. Создать asset-map от semantic IDs/instance index к transforms. Экспорт не обязан содержать 864 тяжёлых mesh; anchors можно хранить в JSON.
7. Привязать действия и cargo к v2 run. Видимые положения и очереди проверять на нескольких timestamp.
8. Добавить low LOD и измерить performance. Лишь затем текстуры/фасад/свет и cinematic camera.

У старого rack-bay внешний размер отличается от нового. Изменять структуру/уровни отдельного модуля, не увеличивать человека или forklift. Для Blender соблюдать преобразование Z-up→glTF Y-up один раз; runtime без второго поворота всей сцены.

## Связанные изменения спецификации

| Было v1 | Стало v2 | Причина |
|---|---|---|
| Один PACK | 3 индукции + 6 PACK + shipping | Раздельные этапы и несколько ресурсов |
| Assignment 20↔20 | 200 активных SKU→200 из 288 pick faces; reserve отдельно | Свободные адреса и несколько уровней не являются новыми SKU |
| Один WALK/PICK/PACK | Cargo transitions, conveyors, blocked states, receiving/dispatch | Настоящий поток вместо декоративной активности |
| Infinite packing queue | 4 tote/post, 40 shipping parcels, 96 tote | Возможны congestion и backpressure |
| Completed=packed | Packed отдельно; completed=dispatched | Отгрузка должна завершать цикл |
| Старые research metrics | Legacy reference, отдельная synthetic evaluation | Нельзя переносить числа на другую систему |
| 0/1/2 swap | 0/2/8, shortlist | Достаточно заметные решения на 200 SKU, ограниченная стоимость |

## Граница этой поставки

Изменены ТЗ, план работ, контракты и проверяемые примеры. Исходный архив не перестроен; новое приложение, GLB, runtime FPS и эффект оптимизации пока не созданы. Эта правка даёт двум исполнителям согласованное новое задание.

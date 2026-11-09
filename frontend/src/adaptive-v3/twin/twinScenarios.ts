/**
 * Scenarios N0–N4 as they stand today: declared, frozen inputs only. Nothing here is a run or an outcome — the V3
 * engine is not connected, so no card states a gain, a time or a winner. Every count and hash below is copied from
 * the fixture named in `source` and re-checked against that file by tools/check-twin-scenario-v3.mjs.
 */
export type ScenarioStatus='frozen'|'candidate'|'described';
export type PortCount={port_id:string;before:number;after:number};
export type ScenarioCard={
 id:'N0'|'N1'|'N2'|'N3'|'N4';title:string;status:ScenarioStatus;idea:string;
 /** What the inputs change against the ordinary shift, in plain words. */
 changes:string[];
 /** What stays identical — the condition that makes A and B comparable. */
 same:string;
 /** Requests per gate before → after, only where the fixture declares port counts. */
 ports?:{inbound:PortCount[];outbound:PortCount[]};
 /** What arrives at a gate, for scenarios without per-gate request counts. */
 gateNotes?:{port_id:string;text:string}[];
 /** Zones to outline and frame on the warehouse when the card is shown. */
 focus:string[];
 /** Fixture file and its payload hash (frozen_payload_sha256 or inputs_sha256). */
 source:{task:string;path:string;sha256:string}|null;
};
export const STATUS_RU:Record<ScenarioStatus,string>={frozen:'Входы зафиксированы',candidate:'Входы на проверке',described:'Только описание'};
export const PORT_RU:Record<string,string>={
 IN_W_BULK:'Приёмка запад · навал',IN_N_STANDARD:'Приёмка север · стандарт',IN_E_PARCEL:'Приёмка восток · посылки',
 OUT_W_RETAIL:'Отгрузка запад · розница',OUT_S_EXPRESS:'Экспресс-отгрузка · юг',OUT_E_B2B:'Отгрузка восток · B2B',
};
export const NOT_RUN='Расчёт не выполнен: движок V3 не подключён. Здесь нет ни выигрыша, ни времени — только условия сравнения.';
const SAME_SLOTTING='530 грузовых единиц, 24 работника, 2 погрузчика, 6 ворот, заявки и сроки — одинаковы для A и B. Меняться может только размещение груза.';

export const SCENARIOS:ScenarioCard[]=[
 {id:'N0',title:'Обычная смена',status:'frozen',idea:'Исходная смесь ворот без изменений. Проверка, что система не переставляет груз ради перестановки: ответ «ничего не менять» допустим.',
  changes:['Входы не меняются: 16 заявок — 8 на приёмку и 8 на отгрузку'],same:SAME_SLOTTING,
  ports:{inbound:[{port_id:'IN_W_BULK',before:5,after:5},{port_id:'IN_N_STANDARD',before:2,after:2},{port_id:'IN_E_PARCEL',before:1,after:1}],
   outbound:[{port_id:'OUT_W_RETAIL',before:3,after:3},{port_id:'OUT_S_EXPRESS',before:1,after:1},{port_id:'OUT_E_B2B',before:4,after:4}]},
  focus:['STAGE_IN_W_BULK','STAGE_IN_N_W','STAGE_IN_N_E','STAGE_IN_E_PARCEL','STAGE_OUT_W_RETAIL','STAGE_OUT_S_EXPRESS','STAGE_OUT_E_B2B'],
  source:{task:'W09',path:'docs/adaptive-v3/fixtures/scenarios/W09-normal-input-v3.json',sha256:'6d5ae65a7c0638a3a3ec266c7398a31e219369b9153cbb986c5f422989ddc8c6'}},
 {id:'N1',title:'Сдвиг исходящего потока',status:'frozen',idea:'Розничная отгрузка на западе уходит на экспресс и восточный B2B. Видно, к каким воротам груз теперь едет.',
  changes:['4 заявки назначены на другие ворота: 3 отгрузки с западной розницы (на экспресс и B2B) и 1 приёмка с севера на восток','Количество, состав и время заявок те же'],same:SAME_SLOTTING,
  ports:{inbound:[{port_id:'IN_W_BULK',before:5,after:5},{port_id:'IN_N_STANDARD',before:2,after:1},{port_id:'IN_E_PARCEL',before:1,after:2}],
   outbound:[{port_id:'OUT_W_RETAIL',before:3,after:0},{port_id:'OUT_S_EXPRESS',before:1,after:2},{port_id:'OUT_E_B2B',before:4,after:6}]},
  focus:['STAGE_OUT_W_RETAIL','STAGE_OUT_S_EXPRESS','STAGE_OUT_E_B2B','STAGE_IN_N_W','STAGE_IN_N_E','STAGE_IN_E_PARCEL'],
  source:{task:'W10',path:'docs/adaptive-v3/fixtures/scenarios/W10-port-mix-input-v3.json',sha256:'af7ff242c6ef0b6e299e3919442ddecf54f9a3d38a3e9ff42084b360b05c5792'}},
 {id:'N2',title:'Тяжёлая приёмка',status:'candidate',idea:'Поток паллет, IBC и тяжёлых коробов на западные ворота навала. Сравнивается, куда их можно положить и каким путём везти погрузчиком.',
  changes:['+12 поступлений через приёмку запад · навал: паллета, IBC и тяжёлый короб по очереди','По одному в минуту с 01:30 до 12:30, срок — 10 минут после поступления','Только погрузчиком с подходящей опорой; дополнительной техники нет'],same:SAME_SLOTTING,
  gateNotes:[{port_id:'IN_W_BULK',text:'+12 тяжёлых'}],
  focus:['STAGE_IN_W_BULK','HEAVY_W','HEAVY_E','FLEX_W','FLEX_E'],
  source:{task:'W11',path:'docs/adaptive-v3/fixtures/scenarios/heavy-inbound/current-input-v3.json',sha256:'807e5f8c3c18ef69de7b5865f01dad2e0ba1dcc09782214dfc67964f8670b55c'}},
 {id:'N3',title:'Длинномер',status:'candidate',idea:'Длинные связки проходят только через большие ворота и встают только в LONG-зоны. Неподходящее место должно объяснимо отклоняться.',
  changes:['+4 длинномера LONG_BUNDLE через большие ворота (7 × 4,5 м) в 03:00, 06:00, 09:00 и 12:00','Срок — 15 минут после поступления','Погрузчик с люлькой-захватом 40 кг и разрешённой ориентацией груза'],same:SAME_SLOTTING,
  gateNotes:[{port_id:'IN_W_BULK',text:'+4 длинномера'}],
  focus:['STAGE_IN_W_BULK','LONG_W','LONG_E'],
  source:{task:'W12',path:'docs/v3/contract-proposals/n2-n3-physical-interfaces-v1/n3-current-input.json',sha256:'6a53bd347411f5e881992b803b30aaa9fc117afe3e299bdf0f9723c6792f8007'}},
 {id:'N4',title:'Перестановка людей',status:'candidate',idea:'Те же 24 человека и тот же поток; в отдельном учебном эпизоде можно проверить разрешённую смену роли, путь и возврат.',
  changes:['У упаковщиков K05 и K06 общий объявленный перерыв; PK05 и PK06 свободны в обоих вариантах','В B исходно обученные P01 и P02 могут перейти на упаковку; передача работы занимает 8 с, переход рассчитан по разрешённому пешеходному графу','Незавершённая работа сохраняется до возврата; seek и сброс восстанавливают исходное распределение','Назначение на занятый пост или без исходного навыка отклоняется с причиной. Проверка доступна в каталоге работников'],
  same:'Поток, размещение, навыки и расписание перерывов одинаковы; новых людей и столов нет.',
  focus:['PACKING_LIGHT_LINE'],source:null},
];

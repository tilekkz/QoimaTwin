# Current execution focus

> **ОСТАНОВЛЕНО ДЛЯ ПЕРЕДАЧИ В НОВЫЙ ЧАТ.** Пользователь завершил разработку в этом чате. Прежний goal удалён (live goal=null), живых субагентов нет. M04, M07.2 и M14.4 остались незавершёнными; их ACTIVE и owner — сохранённая точка работы, а не запущенные процессы. Кандидат forklift-mast-stage ещё не прошёл root acceptance. См. `handoff/README.md`.

User steering2026-11-07: reduce slow workflow, repair visibly detached front-wheel attachment, then continue visual TZ3. This takes priority over additional planning/report expansion.

Root checked i5-12450H/12logical CPUs: one sample30%CPU; free RAM varied1.5–2.2GiB of15.7GiB visible. No Blender/Chrome process was running at that check. Do not infer model-service load or close user applications. After a user interruption check agent status and use followup_task to resume interrupted agents; send_message alone does not restart them.

Wheel attachment repair completed and root reviewed: M14.2/M14.3 PASS again. Cast central ramp, larger axle housing/collars and joined outboard cheeks replace the detached-looking skinny connection. Exposed stub84→9mm; old snapshots preserved. Tyre centres, scale, C08 gear/paths and P01 unchanged; actual clearance/contact and source/GLB views verified. Next people_packing=M14.4 mast, rack_crate=M04 LONGsupport, warehouse_props=M07.2 parcel. This is body/cab acceptance, not a complete forklift/action claim.

Browser lifecycle fix verified: `frontend/tools/capture-stand-v3.mjs` now wraps batch `capture-assets-v3.mjs`, accepting multiple asset IDs in one owned browser. Real body+cab+tote15screens took12.767s total (4.883s captures), including graceful-close deadline and forced owned-server cleanup; process termination confirmed. Old capture had saved its images but stalled during Chrome close. Do not return to per-asset unbounded browser shutdown. `QOIMA_STAND_VIEWS=front,side,rear,quarter,top` adds useful cavity/attachment views without additional browser launches.

Execution stays parallel for independent assets. One queued short Blender/browser GPU task at a time. Root review is one coherent gate per changed asset: actual reference, dimensions/cavity/contacts, four close views, final GLB browser check. Repeat only checks affected by a defect/change. Use conservative-hull proof for new contained fixed body parts; do not recalculate unchanged warehouse route graphs. Keep evidence concise and avoid reopening accepted reference pixels for minor illustration differences when numeric targets are authoritative.

Do not multiply card children or write long new reports for routine steps. Preserve required TZ3 quality gates. Finish assets and scene integration before broadening analysis. Root alone updates board/central state. V2/V3 remain separate; final packages/review guide and publish are still outstanding.

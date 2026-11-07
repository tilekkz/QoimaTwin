# User review and next-session requirements — 2026-11-08

Source: direct user messages and three attached screenshots in the current chat. These corrections take precedence over older hand poses and speculative action plans. The user explicitly requested **no implementation of these changes in this chat**; prepare the handoff first and continue in a new chat.

## Required corrections, not yet implemented

1. In a relaxed/standing pose, both palms face inward toward the legs. Review all role variants, original/template rest poses and reset/dispose poses. Preserve the 1.7m body, connected wrists, real mesh volume and individual actor identity. Do not merely change a screenshot camera.
2. During the demonstrated handle grip, hands hold from above, palm down, rather than from below. User screenshot is the picking-cart handle. Audit other actual grip actions for the same orientation issue. Re-solve hand/arm pose within accepted limits, maintain actual handle contacts and rerun affected gait/grip/native/seek regressions; old passing contact tests do not establish correct palm orientation.
3. User suspects the opening/unfolding of the large outer box shown in screenshot03. The pictured asset is **the outer SMALL handling case in picker-pick-source-fixture**, not necessarily the C02 HEAVY archetype. Inspect actual flap hinges, panel arrangement, seams and clear access against the reference and a plausible carton opening. Current raised whole front panel is a suspect candidate; do not assume its 180-degree fold is visually accepted merely because its surfaces/supports passed native checks. Preserve nominal320x240x240mm closed-HU dimensions and C02 940g/24; fix topology/hinges/open handling envelope before accepting P03.5.2 again. Do not infer a confirmed root cause solely from screenshot03.

## Review evidence

- `assets/v3/user-feedback/2026-11-08/01-rest-palms.png`
- `assets/v3/user-feedback/2026-11-08/02-cart-hands.png`
- `assets/v3/user-feedback/2026-11-08/03-outer-case-opening.png`

The P03.5.2 mechanical/source checks remain historical evidence, but its review is reopened as VERIFY. P03.5.3 remains unimplemented and must wait for the corrected source/hand gates. Earlier P03.1..4/P03.5.1 PASS records describe old accepted technical state; these new orientation requirements require explicit re-review of affected results before final V3 acceptance.

## Night session

User: «на ночь открывать веб версию не нужно, пиши так чтобы была гарантия работы без вылетов».

Do not open the web version or new visible browser windows at night. Existing user tabs may stay open. Use local CLI/background Blender and bounded headless QA where browser verification is required; do not start unnecessary heavy renderers. One heavy Blender/browser task at a time, bounded process timeouts, owned-process cleanup only. Read applicable skills before using them.

A prompt cannot guarantee uninterrupted runtime, prevent host/application crashes or remove session limits. Do not promise overnight execution beyond actual supported runtime. Continue autonomous work for the available session; save exact resume state after each meaningful gate and before long jobs, including current defect, command, source hashes and evidence. Commit/push coherent, validated feature-branch checkpoints (already authorized), and clearly disclose uncompleted work. Do not create shell self-restart loops, scheduled continuation jobs, duplicate chats or automations. No user message is sent to the friend automatically.

## Next order

Read current RESUME/CURRENT_FOCUS and this review first. Diagnose the three corrections before changing more models; declare bounded ownership/cards and keep one ACTIVE task. Correct relaxed palms, then above-handle grip and affected gait, then the carton opening. Revalidate and visually inspect actual GLBs/actions before closing gates. Only then implement P03.5.3 same-instance primary-unit pick and P03.6 loaded-tote handoff, followed by remaining personnel, whole V3 scene, runtime/UX/Q and separate V2/V3 runnable delivery. Do not stop at a checkpoint unless the user asks or a real limit blocks continuation.

Full visual V3 remains incomplete. Arman's backend/DES/planner/ledger is outside our implementation scope. Synthetic visual fixtures are never actual engine runs or inventory changes. Preserve V2 branch and protected shared contracts.

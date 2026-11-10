Two actionable findings from static review; no tools or tests executed.

1. **`createWarehouseScenarioScene.bind` can leave a broken previous binding after rejection.**  
   **Trigger:** Bind scene A, then attempt binding B with different SMALL controllers and an unprepared Source/LONG dependency. A’s controllers are disposed before `SCENARIO_SOURCE_LONG_PLAN_NOT_PREPARED` throws, while `plan` still references A and `snapshot().ready` remains true.  
   **Minimal fix:** Validate all identities, required controllers and prepared dependencies before disposing or resetting anything. Any later construction failure must restore the previous binding or explicitly clear readiness.  
   **Retest:** Reject that rebind, then apply A during outbound and receiving, reverse seek, and dispose. Verify A remains usable and all original resources restore.

2. **`preparePedestrianRoute` / `bind` can reuse stale native gaits.**  
   **Trigger:** Reuse a `route_id` with changed parameters. Direct preparation checks actor and points but ignores `start_yaw_rad` and `speed_m_s`; `bind` skips preparation entirely for cached IDs, also bypassing the points check. The scene can therefore execute a gait inconsistent with the bound route.  
   **Minimal fix:** Always validate cached routes during bind using actor, points, initial yaw and speed; reject changed reuse or recompile the gait.  
   **Retest:** Reuse an ID with changed yaw/speed, then bind another issued plan with changed points under that ID. Require rejection before mutation or correct recompilation, and compare actual actor transforms with sampled DTOs through forward and reverse seeks.

Neither finding establishes a failure in the supplied six-workflow matrix.
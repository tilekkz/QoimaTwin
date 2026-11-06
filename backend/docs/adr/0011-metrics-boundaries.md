# 0011. Metrics boundaries and undefined statistics

Status: accepted for task D, 2026-11-07.

Horizon counts use timestamps strictly less than H; end counts include events at end_tick.
Duration integrals always use [0, cutoff). Final settled queues are observed after dispatch;
service, claimed forklift tasks, and blocked output are excluded from waiting queues.
Receiving WAITING and processed putaway queues are separate; external receipts are separate.
When drain ends before H, the final settled queue sizes persist to H (normally all zero).

Completed means dispatched. Rejected inventory orders remain backlog and are also reported
separately as unfulfilled_inventory. Cycles include only completions observed in the window;
packed cycles have a separate population. P95 uses rank (n-1)*0.95 and linear interpolation.
Empty populations, zero denominators, and makespan without all arrivals dispatched yield null.
Makespan is the last dispatch timestamp from simulation origin, not the forklift return.
Backlog age is cutoff minus arrival; includes rejected orders.

Role utilization counts every roster actor, never vehicles. Active = TRAVEL + BUSY_SERVICE;
BLOCKED and WAIT_RESOURCE are separate. Planned actions are clipped at the cutoff. Unemitted
open induction/output blocks are read from live state without changing the recorder.

Integration: Engine._on_tick_settled records queues after fixed-point dispatch and invariants,
before capturing checkpoints. The observers share one hook.
summary(engine,outcome) lives in app.simulation.metrics_summary and returns JSON-ready values.
The original Metrics.counts() keys and behavior are unchanged.

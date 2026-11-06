# 0006. Pallet state machine

Status: accepted, 2026-11-07.

States: OPEN, SEAL_PENDING, SEALED, CLAIMED, DISPATCHED.

- `placed_count + reserved_slots <= 10` at all times.
- A shipper reserves the parcel and one pallet slot atomically before the scan starts.
- The 300 s age timer starts at the first completed placement.
- At timeout, or when the pallet is full, the pallet becomes SEAL_PENDING. New reservations are refused.
  Reservations already made finish normally.
- The seal happens when `reserved_slots == 0` and the sealed-pallet queue (capacity 8) has space.
  The seal creates exactly one forklift task.
- Each timer carries a generation number. A stale timer callback does nothing.
- There is no early flush at drain. A partial pallet waits for its own timer.
- Dispatch happens when the forklift completes the dock transfer, not at seal and not at return.

Check case D8: scan [296, 304) and timeout at 300 give SEAL_PENDING at 300, then the seal and one task at 304.

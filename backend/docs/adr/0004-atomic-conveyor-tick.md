# 0004. Atomic conveyor tick

Status: accepted, 2026-11-07.

## Decision

1. Read the immutable pre-tick occupancy.
2. For each cargo, find its single legal next position: the next cell, the divert branch for its fixed target,
   or the terminal buffer.
3. Propagate vacancies with a worklist that starts from exits and empty cells. The loop is a cycle,
   so a topological sort is not used.
4. At a merge, a `RoundRobinArbiter` grants at most one contender. The cursor moves only after a successful grant
   and is part of the snapshot.
5. Commit all moves at once. Each old cargo moves at most one cell.
6. Admit new cargo into free inlet cells in stable request order. New cargo first moves on the next tick.

## Rules

- A tote whose target pack buffer is full waits at the divert cell and blocks cargo behind it. There is no recirculation.
- The target pack post is fixed when the tote becomes ready for handoff and never changes.
- Ring occupancy is at most 96 totes on 112 loop cells. A larger tote pool is rejected until a ring-deadlock policy exists.

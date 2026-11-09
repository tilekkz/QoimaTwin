"""Check finite-resource ownership and materialize observed operation intervals."""

from app.v3.interface import Json
from app.v3.run_values import fraction

STAGES = {
    "inbound": [
        "approach_port",
        "intake_service",
        "carry_to_buffer",
        "place_buffer",
        "pickup_buffer",
        "carry_to_slot",
        "place_stock",
        "return_home",
    ],
    "outbound": [
        "approach_stock",
        "pickup_stock",
        "carry_to_buffer",
        "place_buffer",
        "pickup_buffer",
        "carry_to_port",
        "shipping_service",
        "return_home",
    ],
}


class Trace:
    def __init__(self, run: Json) -> None:
        self.run, self.profile = run, run["profile"]
        self.jobs = {j["job_id"]: j for j in self.profile["jobs"]}
        self.ports = {p["port_id"]: p for p in self.profile["ports"]}
        self.units = {h["hu_id"]: h for h in self.profile["handling_units"]}
        self.assigned: dict[str, str] = {}
        for event in run["events"]:
            if event["job"] is not None and event["job"]["actor_id"] is not None:
                job, actor = event["job_id"], event["job"]["actor_id"]
                if self.assigned.setdefault(job, actor) != actor:
                    raise ValueError("manual job cannot switch its exclusive worker")
        self.leases: dict[str, str] = {}
        self.workers = {w["actor_id"]: w for w in run["initial_state"]["workers"]}
        self.owners = {h["hu_id"]: h for h in run["initial_state"]["owners"]}
        self.open: dict[str, Json] = {}
        self.indices: dict[str, int] = {}
        self.operations: list[Json] = []

    def need(self, resource: str, job: str) -> None:
        if self.leases.get(resource) != job:
            raise ValueError("manual operation/ownership lacks its actual exclusive resource lease")

    def event(self, event: Json) -> None:
        job = self.jobs[event["job_id"]]
        for resource in event["resource_ids"]:
            self._resource(event, resource, job)
        if event["worker"] is not None:
            worker = event["worker"]
            if worker["job_id"] is not None:
                self.need("worker:" + worker["actor_id"], job["job_id"])
            self.workers[worker["actor_id"]] = worker
        if event["owner"] is not None:
            self._owner(event, job)
            self.owners[event["hu_id"]] = event["owner"]
        if event["kind"] == "operation_started":
            self._start(event, job)
        elif event["kind"] == "operation_completed":
            self._complete(event)

    def _resource(self, event: Json, resource: str, job: Json) -> None:
        kind, separator, identifier = resource.partition(":")
        port, job_id = self.ports[job["port_id"]], job["job_id"]
        allowed = {
            "worker": {self.assigned.get(job_id)},
            "hu": {job["hu_id"]},
            "port": {job["port_id"]},
            "slot": {job["slot_id"]} if job["direction"] == "inbound" else set(),
            "buffer": {p["place_id"] for p in port["buffer_places"]},
        }
        if not separator or identifier not in allowed.get(kind, set()):
            raise ValueError("manual lease resource does not belong to the actual job")
        if kind == "buffer":
            place = next(p for p in port["buffer_places"] if p["place_id"] == identifier)
            _fit(self.units[job["hu_id"]], place)
        if event["kind"] == "lease_acquired":
            if resource in self.leases:
                raise ValueError("manual resource has overlapping exclusive leases")
            self.leases[resource] = job_id
        else:
            self.need(resource, job_id)
            del self.leases[resource]

    def _owner(self, event: Json, job: Json) -> None:
        owner, job_id = event["owner"], job["job_id"]
        kind, location = owner["kind"], owner["location_id"]
        if kind == "outside":
            if job["direction"] != "inbound" or event["tick"] != job["arrival_tick"]:
                raise ValueError("manual outside ownership requires an actual inbound arrival")
            return
        self.need("hu:" + job["hu_id"], job_id)
        if kind == "worker":
            if location != self.assigned.get(job_id) or location != event["actor_id"]:
                raise ValueError("manual HU ownership does not use its actual leased worker")
            self.need("worker:" + location, job_id)
        elif kind in {"stock", "service", "shipped"}:
            expected = job["slot_id"] if kind == "stock" else job["port_id"]
            if location != expected:
                raise ValueError("manual HU ownership differs from its job destination")
            self.need(("slot:" if kind == "stock" else "port:") + location, job_id)
        elif kind == "buffer":
            self.need("buffer:" + location, job_id)
        else:
            raise ValueError("manual events cannot restore unreleased ownership")

    def _start(self, event: Json, job: Json) -> None:
        job_id, stage = job["job_id"], event["stage"]
        self.need("worker:" + str(event["actor_id"]), job_id)
        if stage != "return_home":
            self.need("hu:" + job["hu_id"], job_id)
        index, stages = self.indices.get(job_id, 0), STAGES[job["direction"]]
        if job_id in self.open or index >= len(stages) or stages[index] != stage:
            raise ValueError("manual operations violate the declared stage sequence")
        duration = self._duration(event, job)
        end = event["tick"] + duration
        if stage in {"intake_service", "shipping_service"}:
            self.need("port:" + job["port_id"], job_id)
            _window(self.ports[job["port_id"]], event["tick"], end, self.run["at_horizon"]["tick"])
        operation = {
            "operation_id": f"OP:{event['seq']}",
            "job_id": job_id,
            "hu_id": job["hu_id"],
            "actor_id": event["actor_id"],
            "stage": stage,
            "start_tick": event["tick"],
            "planned_end_tick": end,
            "observed_end_tick": min(end, self.run["at_end"]["tick"]),
            "completed": False,
            "motion": event["motion"],
        }
        self.open[job_id] = operation
        self.indices[job_id] = index + 1
        self.operations.append(operation)

    def _duration(self, event: Json, job: Json) -> int:
        stage = event["stage"]
        if event["motion"] is not None:
            return int(event["motion"]["end_tick"] - event["tick"])
        if stage.startswith("pickup_"):
            return int(self.profile["handling"]["pickup_ticks"])
        if stage.startswith("place_"):
            return int(self.profile["handling"]["place_ticks"])
        if stage in {"intake_service", "shipping_service"}:
            port, unit = self.ports[job["port_id"]], self.units[job["hu_id"]]
            return int(dict(port["service_ticks"])[unit["archetype"]])
        raise ValueError("manual travel operation lacks its planned actual route")

    def _complete(self, event: Json) -> None:
        operation = self.open.pop(event["job_id"], None)
        if operation is None or operation["stage"] != event["stage"]:
            raise ValueError("manual completion lacks its started operation")
        if operation["planned_end_tick"] != event["tick"]:
            raise ValueError("manual completion differs from its declared operation duration")
        operation["completed"] = True
        operation["observed_end_tick"] = event["tick"]

    def settled(self) -> None:
        seen: set[tuple[str, str]] = set()
        for owner in self.owners.values():
            kind, location = owner["kind"], owner["location_id"]
            if kind not in {"stock", "worker", "buffer", "service"}:
                continue
            if (kind, location) in seen:
                raise ValueError("manual ownership exceeds a finite place/worker resource")
            seen.add((kind, location))
        for worker in self.workers.values():
            if worker["job_id"] is not None:
                self.need("worker:" + worker["actor_id"], worker["job_id"])


def _fit(unit: Json, place: Json) -> None:
    if unit["archetype"] not in place["allowed_archetypes"]:
        raise ValueError("manual buffer lease lacks actual cargo permission")
    if fraction(unit["gross_mass_kg"]) > fraction(place["max_payload_kg"]):
        raise ValueError("manual buffer resource payload exceeded")
    if any(
        fraction(a) > fraction(b)
        for a, b in zip(unit["dimensions_xyz_m"], place["usable_dimensions_xyz_m"], strict=True)
    ):
        raise ValueError("manual buffer resource dimensions exceeded")


def _window(port: Json, start: int, end: int, horizon: int) -> None:
    if not any(a <= start < min(b, horizon) and end <= min(b, horizon) for a, b in port["windows"]):
        raise ValueError("manual service does not complete inside its port window and horizon")


def operation_index(run: Json) -> list[Json]:
    trace = Trace(run)
    events = run["events"]
    for index, event in enumerate(events):
        trace.event(event)
        if index == len(events) - 1 or events[index + 1]["tick"] != event["tick"]:
            trace.settled()
    if any(row["planned_end_tick"] <= run["at_end"]["tick"] for row in trace.open.values()):
        raise ValueError("manual trace omits an operation completion inside observed time")
    return trace.operations


def active_operation_ids(operations: list[Json], tick: int) -> list[str]:
    return [
        row["operation_id"]
        for row in operations
        if row["start_tick"] <= tick
        and (
            tick < row["observed_end_tick"]
            or (not row["completed"] and tick == row["observed_end_tick"])
        )
    ]

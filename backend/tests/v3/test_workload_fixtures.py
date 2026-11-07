"""Tiny declared whole-HU recipes and exact hand demand weights."""

from fractions import Fraction as F

from app.v3.workload_models import DemandWeight, WholeHUTemplate, WorkloadSource


def hand_source() -> WorkloadSource:
    templates = tuple(
        WholeHUTemplate(
            sku,
            "SMALL_CARTON",
            24,
            (F(".32"), F(".24"), F(".24")),
            F(".94"),
            "upright_xyz",
            "initial-lot-" + sku,
            ("initial-HU-" + sku,),
            "d" * 64,
            "e" * 64,
        )
        for sku in ("A", "B")
    )
    return WorkloadSource(
        "hand-fixture",
        "c" * 64,
        (("hand-source", "a" * 64),),
        (("hand-source", "b" * 64),),
        templates,
        (DemandWeight("A", "IN1", F(1)), DemandWeight("B", "IN2", F(1))),
        (DemandWeight("A", "OUT1", F(3)), DemandWeight("B", "OUT2", F(1))),
    )


def policy_document() -> dict[str, object]:
    return {
        "schema_id": "qoima.workload-policy.v3-proposal",
        "schema_version": "0.1.0",
        "horizon_tick": 10,
        "offered_hus": {"inbound": 4, "outbound": 4},
        "calendar": {"kind": "normal", "windows": []},
    }

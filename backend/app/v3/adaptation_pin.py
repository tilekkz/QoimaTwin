"""Separate pin of the six Tilek C11 planning documents (ADR 0054); baseline pin untouched."""

SOURCE_REVISION = "be9b4da9b93b2c99aacfd048b8cd3846c91efc82"
PROVENANCE_SHA256 = "6e1817830a0c179812c5c83d3f35d70ab78b5fe9e48bc25c9c4c8af57e04d8ac"
PREFIX = "docs/v3/contract-proposals/"
INPUT_PATH = PREFIX + "adaptation-input-v3.json"
EVALUATION_PATH = PREFIX + "adaptation-evaluation-v3.json"
HORIZON_PATHS = {
    1: PREFIX + "adapted-assignment-v3.json",
    2: PREFIX + "adapted-assignment-horizon2-v3.json",
    4: PREFIX + "adapted-assignment-horizon4-v3.json",
    8: PREFIX + "adapted-assignment-horizon8-v3.json",
}
HORIZONS = (1, 2, 4, 8)
PERIOD_UNIT = "unclocked_planning_period"
SCENARIO_ID = "N2_DECLARED_PORT_MIX_SHIFT"
SOURCE_KIND = "synthetic_planning_fixture"
ADAPTED_SCHEMA = "qoima.adapted-assignment.v3-planning"
INPUT_SCHEMA = "qoima.adaptation-input.v3-planning"
EVALUATION_SCHEMA = "qoima.adaptation-evaluation.v3-planning"
SCHEMA_VERSION = "0.1.0"
TRANSPORT_GRAPH = {"manual_cart": "walk", "forklift_assisted": "vehicle"}

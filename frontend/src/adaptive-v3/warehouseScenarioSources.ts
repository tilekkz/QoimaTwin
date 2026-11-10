export const WAREHOUSE_SCENARIO_SOURCES={
  "N0": {
    "path": "docs/adaptive-v3/fixtures/scenarios/W09-normal-input-v3.json",
    "url": "/data/v3/scenarios/N0.json",
    "sha256": "8bfd657665c614e0ac0f1db00ecf83191eb70a073af05c89fe5cc3d7623ae88d"
  },
  "N1": {
    "path": "docs/adaptive-v3/fixtures/scenarios/W10-port-mix-input-v3.json",
    "url": "/data/v3/scenarios/N1.json",
    "sha256": "b8ad34e25ff27cd40e4656bef541e6a69aee475f3257b4af8b5695b87d0998b5"
  },
  "N2": {
    "path": "docs/adaptive-v3/fixtures/scenarios/heavy-inbound/current-input-v3.json",
    "url": "/data/v3/scenarios/N2.json",
    "sha256": "0f5f422bd09ade5064159183729e877ba12d5687a78341ec716b1c67410d7ee5"
  },
  "N3": {
    "path": "docs/adaptive-v3/fixtures/scenarios/W12-long-freight-input-v3.json",
    "url": "/data/v3/scenarios/N3.json",
    "sha256": "7aeccbc8b9b980e5170c9bd63dab5d71d12cf56ff762bd9193cd13414d74a60b"
  }
} as const;
export type WarehouseScenarioId=keyof typeof WAREHOUSE_SCENARIO_SOURCES;

import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

const code = ts.transpileModule(await fs.readFile(new URL(
  '../src/adaptive-v3/twin/twinOperationsHud.ts', import.meta.url,
), 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const {operationSummary} = await import('data:text/javascript,' + encodeURIComponent(code));
const frame = (waiting, packed, processing) => ({
  counts: {arrived: 18, waiting, packed, completed: 1, in_service: processing,
    in_transit: 18 - waiting - processing - 1},
  queue: {total: waiting, main: Math.max(0, waiting - 1), upstream: Math.min(1, waiting)},
  stations: Array.from({length: processing}, () => ({status: 'processing'})),
  decision: {applied: true}, outage: {active: true},
});
const input = {A: frame(9, 3, 0), B: frame(3, 9, 2), totalJobs: 18,
  totalWorkers: 24, totalVehicles: 7, helpersTravelling: 0};
const before = structuredClone(input);
const summary = operationSummary(input);
assert.deepEqual(summary.A, {queue: 8, packed: 3, working: 0});
assert.deepEqual(summary.B, {queue: 2, packed: 9, working: 2});
assert.equal(summary.phase, 'draining');
assert.equal(summary.scope, '18 грузов · команда 24 · погрузчиков 7 · демо-сценарий');
assert.deepEqual(input, before);
assert.equal(operationSummary({...input, helpersTravelling: 2}).phase, 'support');
assert.equal(operationSummary({...input, B: frame(0, 18, 0)}).phase, 'packed');
const common = structuredClone({...input, B: input.A});
common.B.decision = {applied: false};
assert.equal(operationSummary(common).phase, 'pressure');
assert.equal(operationSummary(common).A.packed, operationSummary(common).B.packed);
console.log(JSON.stringify({passed: true, readout_cases: 6, packing_stage_scope: true}));

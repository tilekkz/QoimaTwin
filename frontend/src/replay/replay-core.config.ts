import { defineConfig } from '@playwright/test';

// Pure deterministic tests need neither a WebGL browser nor a Vite server.
export default defineConfig({ testDir: '../../tests', testMatch: 'replay-core.spec.ts', outputDir: '../../../work/replay-core-test-results', workers: 1, reporter: 'list' });

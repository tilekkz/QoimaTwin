/** Whole-repository frontend regression against an already built local preview. */
import {defineConfig} from '@playwright/test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.env.QOIMA_TEST_BASE_URL??='http://127.0.0.1:4224';
const resultDir=path.join(frontend,'..','work/v3/full-tz-closeout-20261109/deep-official-regression',new Date().toISOString().replaceAll(/[:.]/g,'-'));
export default defineConfig({
 testDir:path.join(frontend,'tests'),fullyParallel:false,workers:1,timeout:90000,expect:{timeout:20000},
 outputDir:path.join(resultDir,'artifacts'),reporter:[['list'],['json',{outputFile:path.join(resultDir,'results.json')}]],
 use:{channel:'chrome',headless:true,viewport:{width:1366,height:768},launchOptions:{args:['--mute-audio','--no-proxy-server',...(process.platform==='win32'?['--use-angle=d3d11']:[])]}},
});

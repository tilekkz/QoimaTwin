import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const out=path.dirname(fileURLToPath(import.meta.url));
let code=await readFile(path.join(out,'solve.mjs'),'utf8');
code=code.slice(0,code.indexOf('let specs='));
code=code.replaceAll("'search-hashes-before.json'","'validation-hashes-before.json'");
code+=await readFile(path.join(out,'validation-tail.js'),'utf8');
await writeFile(path.join(out,'validate.mjs'),code);

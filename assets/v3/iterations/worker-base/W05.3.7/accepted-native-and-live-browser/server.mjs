import {createServer} from '../../../frontend/node_modules/vite/dist/node/index.js';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {writeFile} from 'node:fs/promises';
const root=path.dirname(fileURLToPath(import.meta.url)),repo=path.resolve(root,'../../..'),frontend=path.join(repo,'frontend');
const server=await createServer({
 configFile:false,root,publicDir:path.join(frontend,'public'),appType:'mpa',
 resolve:{alias:[{find:/^three$/,replacement:path.join(frontend,'node_modules/three/build/three.module.js')},{find:/^three\/(.*)$/,replacement:path.join(frontend,'node_modules/three/$1')}]},
 optimizeDeps:{entries:[path.join(root,'index.html')],include:[]},
 server:{host:'127.0.0.1',port:4193,strictPort:true,hmr:false,open:false,fs:{allow:[repo]},watch:{ignored:['**/*']}},
});
await server.listen();
const info={pid:process.pid,url:'http://127.0.0.1:4193/',root,configFile:false,hmr:false,entry_only:'index.html',publicDir:path.join(frontend,'public')};
await writeFile(path.join(root,'server.pid.json'),JSON.stringify(info,null,2)+'\n');console.log(JSON.stringify(info));
for(const signal of ['SIGINT','SIGTERM'])process.once(signal,async()=>{await server.close();process.exit(0);});

import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,dirname,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'viewer');
const port=Number(process.env.QOIMA_PORT||4180);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.glb':'model/gltf-binary','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.svg':'image/svg+xml'};
const server=http.createServer(async(request,response)=>{
 try{
  const path=decodeURIComponent(new URL(request.url,'http://127.0.0.1').pathname);
  let target=resolve(root,'.'+path);
  if(target!==root&&!target.startsWith(root+sep)){response.writeHead(403).end('Forbidden');return;}
  if((await stat(target)).isDirectory())target=resolve(target,'index.html');
  const data=await readFile(target);response.writeHead(200,{'Content-Type':types[extname(target)]||'application/octet-stream','Cache-Control':'no-cache'});response.end(data);
 }catch{response.writeHead(404,{'Content-Type':'text/plain; charset=utf-8'}).end('File not found');}
});
server.on('error',error=>{console.error('QoimaTwin server: '+error.message);process.exitCode=1;});
server.listen(port,'127.0.0.1',()=>console.log(`QoimaTwin: http://127.0.0.1:${port}  (Ctrl+C to stop)`));

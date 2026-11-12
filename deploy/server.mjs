// Dependency-free, non-root static server. Nothing outside dist can be served.
import http from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(process.env.STATIC_ROOT||fileURLToPath(new URL('./dist/',import.meta.url)));
const types={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.pdf':'application/pdf','.svg':'image/svg+xml'};
const server=http.createServer(async(req,res)=>{
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{'Allow':'GET, HEAD'});return res.end();}
 try{
  const decoded=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(decoded.includes('\0')||decoded.includes('\\'))throw Error('invalid path');
  const relative=decoded==='/'?'index.html':decoded.replace(/^\/+/, '');
  const target=path.resolve(root,relative);
  if(!target.startsWith(root+path.sep))throw Error('outside static root');
  const info=await stat(target);if(!info.isFile())throw Error('not a file');
  res.writeHead(200,{'Content-Type':types[path.extname(target)]||'application/octet-stream','Content-Length':info.size,'X-Content-Type-Options':'nosniff','Cache-Control':path.extname(target)==='.html'?'no-cache':'public, max-age=300'});
  if(req.method==='HEAD')return res.end();
  createReadStream(target).on('error',()=>res.destroy()).pipe(res);
 }catch{res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');}
});
server.listen(Number(process.env.PORT||8080),'0.0.0.0',()=>console.log('Static dashboard listening on PORT '+(process.env.PORT||8080)));

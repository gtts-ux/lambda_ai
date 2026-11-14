// Native integration uses the real controller/helper. Only the HTTP stream is
// supplied by the freshly built release artifact, without publishing a test feed.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {EventEmitter}=require('node:events');
const {prepareUpdate}=require('../updates.cjs');
const options=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const filename=path.basename(options.payload),version=require('../package.json').version;
const release={status:'available',latest:version,filename,bytes:fs.statSync(options.payload).size,
  digest:'sha256:'+crypto.createHash('sha256').update(fs.readFileSync(options.payload)).digest('hex'),
  url:`https://github.com/gtts-ux/lambda_ai/releases/download/desktop-v${version}/${filename}`};
process.stdin.resume();process.stdin.on('end',()=>process.exit(0));
const requester=(_url,_options,callback)=>{
  const request=new EventEmitter();request.setTimeout=()=>{};request.destroy=error=>request.emit('error',error);
  process.nextTick(()=>{const response=fs.createReadStream(options.payload);response.statusCode=200;response.headers={};callback(response);});return request;
};
const progress=[];
prepareUpdate({...options,release,platform:process.platform,env:process.env,requester,onProgress:data=>progress.push(data)})
  .then(result=>fs.writeFileSync(options.prepared,JSON.stringify({...result,progress})))
  .catch(error=>{console.error(error);process.exit(1);});

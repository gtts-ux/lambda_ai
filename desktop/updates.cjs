const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {pipeline} = require('node:stream/promises');
const {Transform} = require('node:stream');
const {spawn} = require('node:child_process');

const REPOSITORY = 'https://github.com/gtts-ux/lambda_ai';
const RELEASES = `${REPOSITORY}/releases`;
function version(value) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(value || '');
  if (!match) throw new Error('Unsupported desktop version.');
  return match.slice(1).map(Number);
}
function compare(a, b) {
  const av = version(a), bv = version(b);
  for (let i=0;i<3;i++) if (av[i]!==bv[i]) return av[i]-bv[i];
  return 0;
}
function fetchReleases() {
  return new Promise((resolve, reject) => {
    const request = https.get('https://api.github.com/repos/gtts-ux/lambda_ai/releases?per_page=100', {
      headers: {'User-Agent':'Lambda-Desktop', Accept:'application/vnd.github+json'}
    }, response => {
      if (response.statusCode!==200) { response.resume(); reject(new Error(`GitHub update check returned HTTP ${response.statusCode}. Try again later.`)); return; }
      let raw='';
      response.setEncoding('utf8');
      response.on('data', chunk => {raw+=chunk;if(raw.length>2000000)request.destroy(new Error('Update response is too large.'));});
      response.on('end', () => {try{resolve(JSON.parse(raw));}catch{reject(new Error('Could not read the desktop release list.'));}});
      response.on('error', reject);
    });
    request.setTimeout(15000, () => request.destroy(new Error('Update check timed out. Check your connection and try again.')));
    request.on('error', reject);
  });
}
async function checkForUpdates(current, platform, arch, fetcher=fetchReleases) {
  version(current);
  const releases=await fetcher();
  if (!Array.isArray(releases)) throw new Error('Could not read the desktop release list.');
  const choices=releases.filter(r=>!r.draft&&!r.prerelease&&/^desktop-v\d+\.\d+\.\d+$/.test(r.tag_name||''));
  choices.sort((a,b)=>compare(b.tag_name.slice(9),a.tag_name.slice(9)));
  if(!choices.length)return {status:'unpublished',current,url:RELEASES};
  const release=choices[0], latest=release.tag_name.slice(9);
  const os={darwin:'macos',win32:'windows',linux:'linux'}[platform];
  const ext={darwin:'zip',win32:'exe',linux:'AppImage'}[platform];
  const nativeArch=platform==='linux'&&arch==='x64'?'x86_64':arch;
  const filename=`Lambda-${latest}-${os}-${nativeArch}.${ext}`;
  const asset=(release.assets||[]).find(a=>a.name===filename&&a.browser_download_url===`${RELEASES}/download/${release.tag_name}/${filename}`);
  const checksum=(release.assets||[]).find(a=>a.name==='SHA256SUMS.txt'&&a.browser_download_url===`${RELEASES}/download/${release.tag_name}/SHA256SUMS.txt`);
  return {status:compare(latest,current)>0?'available':'current',current,latest,
    url:asset?.browser_download_url||`${RELEASES}/tag/${release.tag_name}`,direct:!!asset,
    filename,bytes:asset?.size,digest:asset?.digest,checksumUrl:checksum?.browser_download_url};
}

function trustedURL(value) {
  const url=new URL(value);
  if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443')||
    !['github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(url.hostname))throw new Error('Untrusted update download address.');
  return url;
}
function responseFor(value,requester=https.get,redirects=0) {
  return new Promise((resolve,reject)=>{
    let url;try{url=trustedURL(value);}catch(error){reject(error);return;}
    const req=requester(url,{headers:{'User-Agent':'Lambda-Desktop'}},res=>{
      if([301,302,303,307,308].includes(res.statusCode)){
        res.resume();if(redirects>=5){reject(new Error('Too many update redirects.'));return;}
        try{resolve(responseFor(new URL(res.headers.location,url).href,requester,redirects+1));}catch(error){reject(error);}return;
      }
      if(res.statusCode!==200){res.resume();reject(new Error(`Update download returned HTTP ${res.statusCode}.`));return;}
      resolve(res);
    });
    req.setTimeout(30000,()=>req.destroy(new Error('The update download timed out. Try again.')));req.on('error',reject);
  });
}
async function checksumFor(release,requester=https.get) {
  if(/^sha256:[a-f0-9]{64}$/.test(release.digest||''))return release.digest.slice(7);
  if(!release.checksumUrl)throw new Error('This release has no verified update checksum.');
  const response=await responseFor(release.checksumUrl,requester);let raw='';
  for await(const chunk of response){raw+=chunk.toString('utf8');if(raw.length>65536){response.destroy();throw new Error('The checksum list is too large.');}}
  const found=raw.split(/\r?\n/).map(line=>/^([a-f0-9]{64})\s+\*?(.+)$/.exec(line)).find(m=>m&&m[2]===release.filename);
  if(!found)throw new Error('The update checksum is missing from the release.');return found[1];
}
async function downloadVerified(release,destination,sha256,onProgress=()=>{},requester=https.get) {
  if(!Number.isSafeInteger(release.bytes)||release.bytes<1||release.bytes>600*1024*1024)throw new Error('Unsupported update package size.');
  const response=await responseFor(release.url,requester);
  const hash=crypto.createHash('sha256');let received=0;
  const verify=new Transform({transform(chunk,_encoding,callback){received+=chunk.length;if(received>release.bytes){callback(new Error('The update is larger than expected.'));return;}hash.update(chunk);onProgress(Math.floor(received/release.bytes*100));callback(null,chunk);}});
  try{
    await pipeline(response,verify,fs.createWriteStream(destination,{flags:'wx',mode:0o600}));
    if(received!==release.bytes||hash.digest('hex')!==sha256)throw new Error('The update is incomplete or its checksum did not match. Your application was not changed.');
  }catch(error){await fs.promises.rm(destination,{force:true});throw error;}
}
function installTarget(platform,executable,env=process.env) {
  if(platform==='darwin'){
    const target=path.resolve(executable,'../../..');
    if(!target.endsWith('.app'))throw new Error('Run the installed Lambda application to update it.');
    return target;
  }
  if(platform==='win32')return executable;
  if(platform==='linux'&&env.APPIMAGE)return path.resolve(env.APPIMAGE);
  throw new Error('Open the Lambda AppImage to use in-app updates.');
}
async function waitForReady(file,child) {
  const end=Date.now()+150000;
  while(Date.now()<end){
    try{const status=JSON.parse(await fs.promises.readFile(file,'utf8'));if(status.ready)return;throw new Error(status.message||'The updater could not prepare the application.');}
    catch(error){if(error.code!=='ENOENT')throw error;}
    if(child.exitCode!==null)throw new Error('The updater stopped before the application could be prepared.');
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw new Error('Preparing the application update timed out.');
}
async function copyRuntime(source,destination) {
  await fs.promises.cp(source,destination,{recursive:true,verbatimSymlinks:true});
}
async function prepareUpdate({release,platform,executable,engine,cache,result,onProgress,env=process.env,requester=https.get}) {
  const target=installTarget(platform,executable,env);
  await fs.promises.access(path.dirname(target),fs.constants.W_OK);
  await fs.promises.mkdir(cache,{recursive:true,mode:0o700});
  const directory=await fs.promises.mkdtemp(path.join(cache,'update-'));
  let helper;
  try{
    onProgress({phase:'downloading',percent:0,version:release.latest});
    const sha256=await checksumFor(release,requester),payload=path.join(directory,release.filename);
    let last=-1;
    await downloadVerified(release,payload,sha256,percent=>{if(percent!==last){last=percent;onProgress({phase:'downloading',percent,version:release.latest});}},requester);
    onProgress({phase:'preparing',percent:100,version:release.latest});
    const runtime=path.join(directory,'runtime');await copyRuntime(path.dirname(engine),runtime);
    const job={pid:process.pid,target,payload,sha256,version:release.latest,token:crypto.randomBytes(32).toString('hex'),
      receipt:path.join(directory,'receipt.json'),ready:path.join(directory,'ready.json'),result};
    const config=path.join(directory,'job.json');await fs.promises.writeFile(config,JSON.stringify(job),{mode:0o600});
    const log=fs.openSync(path.join(directory,'helper.log'),'a',0o600);
    try{helper=spawn(path.join(runtime,path.basename(engine)),['--apply-desktop-update',config],{detached:true,stdio:['ignore',log,log],windowsHide:true,env});}finally{fs.closeSync(log);}
    let spawnError;helper.on('error',error=>{spawnError=error;});
    await new Promise(resolve=>setTimeout(resolve,100));if(spawnError)throw spawnError;
    await waitForReady(job.ready,helper);helper.unref();
    return {version:release.latest,helperPid:helper.pid};
  }catch(error){if(helper&&helper.exitCode===null)helper.kill();await fs.promises.rm(directory,{recursive:true,force:true}).catch(()=>{});throw error;}
}
module.exports={checkForUpdates,compare,trustedURL,checksumFor,downloadVerified,installTarget,prepareUpdate,copyRuntime};

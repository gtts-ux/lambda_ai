const {test}=require('node:test');
const assert=require('node:assert/strict');
const {checkForUpdates}=require('../updates.cjs');
const {trustedURL,checksumFor,downloadVerified,installTarget}=require('../updates.cjs');
const {Readable}=require('node:stream');
const {EventEmitter}=require('node:events');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const url='https://github.com/gtts-ux/lambda_ai/releases/download/desktop-v1.2.0/Lambda-1.2.0-windows-x64.exe';
test('desktop check ignores newer model and CLI releases and picks native asset',async()=>{
  const result=await checkForUpdates('1.1.0','win32','x64',async()=>[
    {tag_name:'v9.0.0'},{tag_name:'model-terra-9'},{tag_name:'desktop-v9.0.0',prerelease:true},
    {tag_name:'desktop-v1.2.0',assets:[{name:'Lambda-1.2.0-windows-x64.exe',browser_download_url:url}]}]);
  assert.equal(result.status,'available');assert.equal(result.url,url);assert.equal(result.direct,true);
});
test('current version stays current; foreign asset links are never used',async()=>{
  const result=await checkForUpdates('1.2.0','win32','x64',async()=>[
    {tag_name:'desktop-v1.2.0',assets:[{name:'Lambda-1.2.0-windows-x64.exe',browser_download_url:'https://example.com/unsafe.exe'}]}]);
  assert.equal(result.status,'current');assert.equal(result.direct,false);assert(result.url.endsWith('/tag/desktop-v1.2.0'));
});
test('network failures are reported rather than claiming up-to-date',async()=>{
  await assert.rejects(checkForUpdates('1.1.0','linux','x64',async()=>{throw new Error('Offline');}),/Offline/);
});
test('Linux x64 checks use the native x86_64 AppImage filename',async()=>{
  const filename='Lambda-1.2.0-linux-x86_64.AppImage';
  const url=`https://github.com/gtts-ux/lambda_ai/releases/download/desktop-v1.2.0/${filename}`;
  const result=await checkForUpdates('1.1.1','linux','x64',async()=>[{tag_name:'desktop-v1.2.0',assets:[{name:filename,browser_download_url:url}]}]);
  assert.equal(result.url,url);assert.equal(result.direct,true);
});
function network(body,statusCode=200,headers={}){return (_url,_options,callback)=>{const req=new EventEmitter();req.setTimeout=()=>{};req.destroy=error=>req.emit('error',error);process.nextTick(()=>{const res=Readable.from([body]);res.statusCode=statusCode;res.headers=headers;callback(res);});return req;};}
test('updater rejects foreign hosts, insecure redirects and embedded credentials',async()=>{
  for(const url of ['http://github.com/update','https://evil.example/file','https://user:pass@github.com/file'])assert.throws(()=>trustedURL(url),/Untrusted/);
  await assert.rejects(checksumFor({checksumUrl:url},network('',302,{location:'http://evil.example/file'})),/Untrusted/);
});
test('download checks both exact length and checksum before allowing installation',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lambda-download-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const body=Buffer.from('verified native application'),sha=crypto.createHash('sha256').update(body).digest('hex');
  const release={url,bytes:body.length};const file=path.join(dir,'update.exe');let progress=0;
  await downloadVerified(release,file,sha,p=>progress=p,network(body));assert.equal(fs.readFileSync(file).toString(),body.toString());assert.equal(progress,100);
  for(const [bytes,digest] of [[body.length, '0'.repeat(64)],[body.length+1,sha],[body.length-1,sha]]){
    const bad=path.join(dir,'bad.exe');await assert.rejects(downloadVerified({...release,bytes},bad,digest,()=>{},network(body)));assert(!fs.existsSync(bad));
  }
});
test('checksum list must name the exact selected native package',async()=>{
  const digest='a'.repeat(64),release={filename:'Lambda.exe',checksumUrl:url};
  assert.equal(await checksumFor(release,network(`${digest}  Lambda.exe\n`)),digest);
  await assert.rejects(checksumFor(release,network(`${digest}  Other.exe\n`)),/missing/);
});
test('application replacement location is derived from this installation',()=>{
  if(process.platform==='darwin')assert.equal(installTarget('darwin','/Users/test/Apps/Lambda.app/Contents/MacOS/Lambda'),'/Users/test/Apps/Lambda.app');
  assert.equal(installTarget('linux','/tmp/mount/lambda-desktop',{APPIMAGE:path.resolve('my-app.AppImage')}),path.resolve('my-app.AppImage'));
  assert.throws(()=>installTarget('linux','/tmp/mount/lambda-desktop',{}),/AppImage/);
});

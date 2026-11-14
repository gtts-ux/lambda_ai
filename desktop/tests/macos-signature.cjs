// Test the distributed ZIP rather than only the unquarantined build directory.
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const assert=require('node:assert/strict');
if(process.platform!=='darwin')throw Error('This test requires macOS.');
const root=path.resolve(__dirname,'..'),version=require('../package.json').version;
const zip=path.join(root,'release',`Lambda-${version}-macos-${process.arch}.zip`);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'lambda-signature-'));
function run(command,args){const result=spawnSync(command,args,{encoding:'utf8',timeout:120000});if(result.status!==0)throw Error((result.stderr||result.stdout||String(result.error)).trim());return result;}
function verify(file,deep=false){run('/usr/bin/codesign',['--verify',...(deep?['--deep']:[]),'--strict','--verbose=2',file]);}
const magics=new Set(['cffaedfe','cefaedfe','feedfacf','feedface','cafebabe','bebafeca','cafebabf','bfbafeca']);
function binaries(directory){const found=[];for(const item of fs.readdirSync(directory,{withFileTypes:true})){const file=path.join(directory,item.name);if(item.isDirectory())found.push(...binaries(file));else if(item.isFile()){const fd=fs.openSync(file,'r'),header=Buffer.alloc(4);try{fs.readSync(fd,header,0,4,0);}finally{fs.closeSync(fd);}if(magics.has(header.toString('hex')))found.push(file);}}return found;}
try{
  run('/usr/bin/ditto',['-x','-k',zip,temp]);
  const extracted=path.join(temp,'Lambda.app');verify(extracted,true);
  const native=process.arch==='x64'?'x86_64':process.arch;
  for(const file of ['Contents/MacOS/Lambda','Contents/Resources/backend/lambda-backend']){
    const arch=run('/usr/bin/lipo',['-archs',path.join(extracted,file)]).stdout.trim().split(/\s+/);
    assert(arch.includes(native),`${file} must include ${native}`);
  }
  const all=binaries(extracted);assert(all.length>10,'Expected Electron, Python and native dependencies.');
  for(const file of all)verify(file);
  const moved=path.join(temp,'Moved application');fs.mkdirSync(moved);const app=path.join(moved,'Lambda.app');fs.renameSync(extracted,app);
  verify(app,true);
  // Chrome's quarantine marker must not invalidate the bundle signature.
  run('/usr/bin/xattr',['-w','com.apple.quarantine','0083;65500000;LambdaSignatureTest;',app]);verify(app,true);
  const info=run('/usr/bin/codesign',['-dv','--verbose=2',app]).stderr;
  assert(info.includes('Signature=adhoc'),'Community build should explicitly carry its local signature.');
  fs.appendFileSync(path.join(app,'Contents/Resources/app.asar'),Buffer.from([0]));
  const damaged=spawnSync('/usr/bin/codesign',['--verify','--deep','--strict',app],{encoding:'utf8'});
  assert.notEqual(damaged.status,0,'A modified app must fail validation.');
  const report={passed:true,version,arch:process.arch,checkedNativeBinaries:all.length,zipSignatureValid:true,
    relocatedSignatureValid:true,quarantinedSignatureValid:true,tamperingRejected:true,notarized:false,
    note:'Ad-hoc signing fixes integrity/missing-resource failures. It does not establish Apple Developer ID trust; downloaded builds can still need Open Anyway.'};
  fs.mkdirSync(path.join(root,'test-artifacts'),{recursive:true});fs.writeFileSync(path.join(root,'test-artifacts','macos-signature.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
}finally{fs.rmSync(temp,{recursive:true,force:true});}

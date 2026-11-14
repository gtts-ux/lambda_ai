const {test}=require('node:test');
const assert=require('node:assert/strict');
const {checkForUpdates}=require('../updates.cjs');
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

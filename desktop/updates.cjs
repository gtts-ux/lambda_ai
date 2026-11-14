const https = require('node:https');

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
  const filename=`Lambda-${latest}-${os}-${arch}.${ext}`;
  const asset=(release.assets||[]).find(a=>a.name===filename&&a.browser_download_url===`${RELEASES}/download/${release.tag_name}/${filename}`);
  return {status:compare(latest,current)>0?'available':'current',current,latest,
    url:asset?.browser_download_url||`${RELEASES}/tag/${release.tag_name}`,direct:!!asset};
}
module.exports={checkForUpdates,compare};

const { app, BrowserWindow, ipcMain, shell, Menu, nativeTheme, dialog } = require('electron');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const fs = require('node:fs');
const path = require('node:path');
const { checkForUpdates, installTarget, prepareUpdate } = require('./updates.cjs');

const METHODS = new Set(['state','send','stop','regenerate','new_chat','open_chat','rename_chat','pin_chat','archive_chat','restore_chat','delete_chat','list_chats','select_model','download','cancel_download','refresh_catalog','preferences','desktop_info','check_updates','install_update']);
for(const method of ['generate_image','delete_image','refresh_image_catalog'])METHODS.add(method);
let window, backend, ready, sequence = 0, quitting = false, updating = false;
const pending = new Map();
if (process.env.LAMBDA_DATA_HOME) {
  const stateDir = path.join(process.env.LAMBDA_DATA_HOME,'desktop-shell');
  fs.mkdirSync(stateDir,{recursive:true}); app.setPath('userData',stateDir);
}
const updateReceipt=process.env.LAMBDA_UPDATE_RECEIPT,updateToken=process.env.LAMBDA_UPDATE_TOKEN;
delete process.env.LAMBDA_UPDATE_RECEIPT;delete process.env.LAMBDA_UPDATE_TOKEN;
function confirmUpdate(){
  if(updateReceipt&&/^[a-f0-9]{64}$/.test(updateToken||'')){
    fs.writeFileSync(updateReceipt,JSON.stringify({token:updateToken,version:app.getVersion()}),{mode:0o600});
  }
}
function updateSupport(){
  try{if(!app.isPackaged)throw new Error('In-app updates are available in the installed application.');installTarget(process.platform,app.getPath('exe'));return {installable:true};}
  catch(error){return {installable:false,reason:error.message};}
}
function lastUpdate(){try{return JSON.parse(fs.readFileSync(path.join(app.getPath('userData'),'desktop-update-result.json'),'utf8'));}catch{return null;}}
async function cleanUpdateCache(){
  const cache=path.join(app.getPath('userData'),'updates-cache');
  for(const entry of await fs.promises.readdir(cache,{withFileTypes:true}).catch(()=>[])){
    if(!entry.isDirectory()||!entry.name.startsWith('update-'))continue;
    const directory=path.join(cache,entry.name),info=await fs.promises.stat(directory).catch(()=>null);
    if(info&&Date.now()-info.mtimeMs>86400000)await fs.promises.rm(directory,{recursive:true,force:true}).catch(()=>{});
  }
}

function engineCommand() {
  const name = process.platform === 'win32' ? 'lambda-backend.exe' : 'lambda-backend';
  const bundled = app.isPackaged ? path.join(process.resourcesPath,'backend',name) : path.join(__dirname,'backend-dist','lambda-backend',name);
  if (fs.existsSync(bundled)) return [bundled, []];
  if (app.isPackaged) throw new Error('The local engine is missing from this application. Reinstall Lambda.');
  const buildPython = path.join(__dirname,'.build-venv',process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const python = process.env.LAMBDA_PYTHON || buildPython;
  if (!fs.existsSync(python)) throw new Error('Build the desktop engine first: npm run build:backend.');
  return [python, [path.join(__dirname,'backend.py')]];
}

function startBackend() {
  ready = new Promise((resolve,reject) => {
    let command, args;
    try { [command,args] = engineCommand(); } catch (error) { reject(error); return; }
    backend = spawn(command,args,{ stdio:['pipe','pipe','pipe'],windowsHide:true,
      env:{...process.env, PYTHONUNBUFFERED:'1', PYTHONUTF8:'1', PYTHONIOENCODING:'utf-8', OMP_NUM_THREADS:'2', OPENBLAS_NUM_THREADS:'2'} });
    const lines = createInterface({input:backend.stdout});
    lines.on('line',line => {
      let data;
      try { data = JSON.parse(line); } catch { return; }
      if (data.event === 'ready') resolve(data.data);
      if (data.event) window?.webContents.send('lambda:event',data);
      if (data.id && pending.has(data.id)) {
        const request = pending.get(data.id); pending.delete(data.id);
        if (data.error) request.reject(new Error(data.error)); else request.resolve(data.result);
      }
    });
    backend.stderr.on('data',chunk => process.stderr.write(chunk));
    backend.once('error',reject);
    backend.once('exit',(code) => {
      const error = new Error('The local engine stopped. Restart Lambda to reconnect.');
      reject(error); for (const request of pending.values()) request.reject(error); pending.clear();
      if (!quitting) window?.webContents.send('lambda:event',{event:'engine-error',data:{message:error.message,code}});
    });
  });
  ready.catch(() => {});
}

function request(method,params={}) {
  return ready.then(() => new Promise((resolve,reject) => {
    const id = ++sequence; pending.set(id,{resolve,reject});
    backend.stdin.write(JSON.stringify({id,method,params})+'\n',error => {
      if (error) { pending.delete(id); reject(error); }
    });
  }));
}

async function createWindow() {
  window = new BrowserWindow({title:'Lambda',width:1240,height:820,minWidth:760,minHeight:560,
    icon:path.join(__dirname,'assets','icon.png'),
    titleBarStyle:process.platform==='darwin' ? 'hiddenInset' : 'default',
    trafficLightPosition:{x:20,y:20},backgroundColor:nativeTheme.shouldUseDarkColors ? '#262624' : '#faf9f6',
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,spellcheck:false}});
  window.webContents.setWindowOpenHandler(() => ({action:'deny'}));
  window.webContents.on('will-navigate',event => event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_wc,_permission,callback) => callback(false));
  await window.loadFile(path.join(__dirname,'renderer','index.html'));
  window.on('closed',() => { window = null; if (process.platform !== 'darwin') app.quit(); });
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance',() => { if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); } });
  app.whenReady().then(async () => {
    // Native-update CI launches the actual replacement binary without inference.
    if(process.env.LAMBDA_UPDATE_TEST==='1'&&updateReceipt){confirmUpdate();app.quit();return;}
    cleanUpdateCache().catch(()=>{});
    const menu = [{label:'Lambda',submenu:[{role:'about'},{type:'separator'},
      {label:'Settings…',accelerator:'CmdOrCtrl+,',click:() => window?.webContents.send('lambda:event',{event:'navigate',data:{view:'settings'}})},
      {type:'separator'},{role:'hide'},{role:'hideOthers'},{role:'unhide'},{type:'separator'},{role:'quit'}]},
      {label:'File',submenu:[{label:'New Chat',accelerator:'CmdOrCtrl+N',click:() => window?.webContents.send('lambda:event',{event:'navigate',data:{view:'new'}})},{role:'close'}]},
      {role:'editMenu'},{role:'viewMenu'},{role:'windowMenu'}];
    Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
    ipcMain.handle('lambda:request',async (event,method,params) => {
      if (event.sender !== window?.webContents || !METHODS.has(method)) throw new Error('Unsupported desktop operation.');
      if (JSON.stringify(params||{}).length > 100000) throw new Error('Request too large.');
      if (method==='desktop_info') return {version:app.getVersion(),platform:process.platform,arch:process.arch,lastUpdate:lastUpdate()};
      if (method==='check_updates') return {...await checkForUpdates(app.getVersion(),process.platform,process.arch),...updateSupport()};
      if (method==='install_update') {
        if(updating)throw new Error('An application update is already running.');
        const support=updateSupport();if(!support.installable)throw new Error(support.reason);
        updating=true;
        try{
          const state=await request('state');if(state.generating||state.downloading)throw new Error('Finish or stop the current reply or model download before updating.');
          const release=await checkForUpdates(app.getVersion(),process.platform,process.arch);
          if(release.status!=='available'||!release.direct)throw new Error('No newer application package is available for this device.');
          const [engine,args]=engineCommand();if(args.length)throw new Error('Run the installed application to update it.');
          await prepareUpdate({release,platform:process.platform,executable:app.getPath('exe'),engine,
            cache:path.join(app.getPath('userData'),'updates-cache'),result:path.join(app.getPath('userData'),'desktop-update-result.json'),
            onProgress:data=>window?.webContents.send('lambda:event',{event:'application-update',data})});
          window?.webContents.send('lambda:event',{event:'application-update',data:{phase:'restarting',version:release.latest,percent:100}});
          setTimeout(()=>app.quit(),350);return {restarting:true};
        }catch(error){updating=false;window?.webContents.send('lambda:event',{event:'application-update',data:{phase:'error',message:error.message}});throw error;}
      }
      if(updating&&['send','regenerate','download','generate_image'].includes(method))throw new Error('The application is preparing an update. Please wait for the restart.');
      return request(method,params);
    });
    ipcMain.handle('lambda:external',async (event,url) => {
      if (event.sender !== window?.webContents) return;
      const parsed = new URL(url);
      if (!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password) throw new Error('Only web links can be opened.');
      await shell.openExternal(parsed.href);
    });
    ipcMain.handle('lambda:image-save',async(event,id)=>{
      if(event.sender!==window?.webContents||typeof id!=='string'||! /^[a-f0-9]{32}$/.test(id))throw new Error('Invalid image.');
      const image=await request('image_png',{id});const raw=Buffer.from(image.base64,'base64');
      if(raw.length>1048576||!raw.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))throw new Error('Invalid PNG.');
      const target=await dialog.showSaveDialog(window,{defaultPath:path.join(app.getPath('downloads'),image.filename),filters:[{name:'PNG image',extensions:['png']}]});
      if(!target.canceled&&target.filePath)await fs.promises.writeFile(target.filePath,raw);
      return {saved:!target.canceled};
    });
    startBackend(); await createWindow();ready.then(confirmUpdate).catch(()=>{});
    app.on('activate',() => { if (!window) createWindow(); else window.show(); });
  });
  app.on('before-quit',event => {
    if (quitting) return;
    event.preventDefault(); quitting = true; window?.hide();
    // Keep the parent alive briefly so EOF can cancel and settle shared usage.
    if (!backend || backend.exitCode !== null) { app.exit(); return; }
    const fallback=setTimeout(() => { backend.kill(); app.exit(); },5000);
    backend.once('exit',() => { clearTimeout(fallback); app.exit(); });
    backend.stdin.end();
  });
}

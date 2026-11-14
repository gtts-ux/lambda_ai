const { app, BrowserWindow, ipcMain, shell, Menu, nativeTheme } = require('electron');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const fs = require('node:fs');
const path = require('node:path');
const { checkForUpdates } = require('./updates.cjs');

const METHODS = new Set(['state','send','stop','regenerate','new_chat','open_chat','rename_chat','pin_chat','archive_chat','restore_chat','delete_chat','list_chats','select_model','download','cancel_download','refresh_catalog','preferences','desktop_info','check_updates']);
let window, backend, ready, sequence = 0, quitting = false;
const pending = new Map();
if (process.env.LAMBDA_DATA_HOME) {
  const stateDir = path.join(process.env.LAMBDA_DATA_HOME,'desktop-shell');
  fs.mkdirSync(stateDir,{recursive:true}); app.setPath('userData',stateDir);
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
    const menu = [{label:'Lambda',submenu:[{role:'about'},{type:'separator'},
      {label:'Settings…',accelerator:'CmdOrCtrl+,',click:() => window?.webContents.send('lambda:event',{event:'navigate',data:{view:'settings'}})},
      {type:'separator'},{role:'hide'},{role:'hideOthers'},{role:'unhide'},{type:'separator'},{role:'quit'}]},
      {label:'File',submenu:[{label:'New Chat',accelerator:'CmdOrCtrl+N',click:() => window?.webContents.send('lambda:event',{event:'navigate',data:{view:'new'}})},{role:'close'}]},
      {role:'editMenu'},{role:'viewMenu'},{role:'windowMenu'}];
    Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
    ipcMain.handle('lambda:request',async (event,method,params) => {
      if (event.sender !== window?.webContents || !METHODS.has(method)) throw new Error('Unsupported desktop operation.');
      if (JSON.stringify(params||{}).length > 100000) throw new Error('Request too large.');
      if (method==='desktop_info') return {version:app.getVersion(),platform:process.platform,arch:process.arch};
      if (method==='check_updates') return checkForUpdates(app.getVersion(),process.platform,process.arch);
      return request(method,params);
    });
    ipcMain.handle('lambda:external',async (event,url) => {
      if (event.sender !== window?.webContents) return;
      const parsed = new URL(url);
      if (!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password) throw new Error('Only web links can be opened.');
      await shell.openExternal(parsed.href);
    });
    startBackend(); await createWindow();
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

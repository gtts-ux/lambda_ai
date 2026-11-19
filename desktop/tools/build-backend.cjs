const { spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const root=path.resolve(__dirname,'..');
const python=process.env.LAMBDA_BUILD_PYTHON || path.join(root,'.build-venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!fs.existsSync(python))throw new Error('Create desktop/.build-venv and install requirements-build.txt first.');
const project=path.dirname(root);
const args=['-m','PyInstaller','--noconfirm','--clean','--onedir','--name','lambda-backend',
  '--distpath',path.join(root,'backend-dist'),'--workpath',path.join(root,'backend-build'),
  '--specpath',path.join(root,'backend-build'),'--paths',project,
  '--collect-submodules','lambda_cli','--collect-data','lambda_cli',
  '--add-data',path.join(project,'lambda_cli','assets')+path.delimiter+'lambda_cli/assets',
  '--exclude-module','tkinter','--exclude-module','torch','--exclude-module','matplotlib',path.join(root,'backend.py')];
const result=spawnSync(python,args,{cwd:root,stdio:'inherit'});
if(result.status!==0)process.exit(result.status||1);
// Only the tiny bundled starter is included. User/downloaded model files and
// training checkpoints are outside this build tree and are never packaged.
const bundle=path.join(root,'backend-dist','lambda-backend');
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const models=walk(bundle).filter(p=>p.endsWith('.npz'));
if(JSON.stringify(models.map(p=>path.basename(p)).sort())!==JSON.stringify(['image_intent.npz','model.npz']))throw new Error('Unexpected model files in desktop engine bundle.');
if(walk(bundle).some(p=>p.endsWith('.pt')||p.endsWith('.sqlite3')))throw new Error('Private training/user data found in application bundle.');
console.log('Desktop engine ready. Small chat starter and learned tool head bundled; image models stay optional.');

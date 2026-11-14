const { app, BrowserWindow, nativeImage }=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const { spawnSync }=require('node:child_process');
app.disableHardwareAcceleration();
app.whenReady().then(async()=>{
  const folder=path.resolve(__dirname,'../assets');fs.mkdirSync(folder,{recursive:true});
  const win=new BrowserWindow({width:1024,height:1024,show:false,frame:false,transparent:true,backgroundColor:'#00000000',webPreferences:{offscreen:true,contextIsolation:true,sandbox:true}});
  await win.loadURL('data:text/html,<html><body></body></html>');
  // Render SVG into a canvas, rather than capturing a native window: Windows
  // offscreen window captures can flatten transparency against an opaque surface.
  const svg='data:image/svg+xml;base64,'+fs.readFileSync(path.join(folder,'logo.svg')).toString('base64');
  const pngData=await win.webContents.executeJavaScript(`(async()=>{const image=new Image();image.src=${JSON.stringify(svg)};await image.decode();const canvas=document.createElement('canvas');canvas.width=canvas.height=1024;canvas.getContext('2d').drawImage(image,0,0,1024,1024);return canvas.toDataURL('image/png');})()`);
  const source=nativeImage.createFromDataURL(pngData);
  const bitmap=source.toBitmap(),size=source.getSize();
  const alpha=(x,y)=>bitmap[(y*size.width+x)*4+3];
  if(alpha(0,0)!==0||alpha(size.width-1,size.height-1)!==0||alpha(Math.floor(size.width*.2),Math.floor(size.height*.5))!==255)throw new Error('Logo corners must be transparent and the orange tile opaque.');
  fs.writeFileSync(path.join(folder,'icon.png'),source.toPNG());
  // Windows supports PNG-compressed 256px images inside a standard ICO.
  const png=source.resize({width:256,height:256,quality:'best'}).toPNG();
  const header=Buffer.alloc(22);header.writeUInt16LE(1,2);header.writeUInt16LE(1,4);
  header.writeUInt16LE(1,10);header.writeUInt16LE(32,12);
  header.writeUInt32LE(png.length,14);header.writeUInt32LE(22,18);
  fs.writeFileSync(path.join(folder,'icon.ico'),Buffer.concat([header,png]));
  if(process.platform==='darwin'){
    const icons=path.join(folder,'icon.iconset');fs.mkdirSync(icons,{recursive:true});
    for(const n of [16,32,128,256,512]){
      fs.writeFileSync(path.join(icons,`icon_${n}x${n}.png`),source.resize({width:n,height:n,quality:'best'}).toPNG());
      fs.writeFileSync(path.join(icons,`icon_${n}x${n}@2x.png`),source.resize({width:n*2,height:n*2,quality:'best'}).toPNG());
    }
    const result=spawnSync('/usr/bin/iconutil',['-c','icns',icons,'-o',path.join(folder,'icon.icns')],{stdio:'inherit'});
    if(result.status)throw new Error('Could not build the macOS icon.');
  }
  win.destroy();app.quit();
}).catch(error=>{console.error(error);app.exit(1);});

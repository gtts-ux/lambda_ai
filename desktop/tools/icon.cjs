const { app, nativeImage }=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const { spawnSync }=require('node:child_process');
app.disableHardwareAcceleration();
app.whenReady().then(async()=>{
  const folder=path.resolve(__dirname,'../assets');fs.mkdirSync(folder,{recursive:true});
  const source=nativeImage.createFromPath(path.join(folder,'logo.jpg'));
  if(source.isEmpty())throw new Error('The supplied Lambda logo is missing.');
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
  app.quit();
}).catch(error=>{console.error(error);app.exit(1);});

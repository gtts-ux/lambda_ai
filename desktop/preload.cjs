const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('lambda', {
  request:(method,params={}) => ipcRenderer.invoke('lambda:request',method,params),
  onEvent:callback => {
    const handler=(_event,payload) => callback(payload);
    ipcRenderer.on('lambda:event',handler);
    return () => ipcRenderer.removeListener('lambda:event',handler);
  },
  openExternal:url => ipcRenderer.invoke('lambda:external',url),
  saveImage:id => ipcRenderer.invoke('lambda:image-save',id),
  platform:process.platform
});

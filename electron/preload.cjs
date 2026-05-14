const { contextBridge, ipcRenderer } = require('electron');

window.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('electron-shell', `platform-${process.platform}`);
});

contextBridge.exposeInMainWorld('decklensRuntime', {
  getStatus: () => ipcRenderer.invoke('runtime:get-status'),
  install: () => ipcRenderer.invoke('runtime:install'),
  start: () => ipcRenderer.invoke('runtime:start'),
  updates: {
    getStatus: () => ipcRenderer.invoke('updates:get-status'),
    check: () => ipcRenderer.invoke('updates:check'),
    download: () => ipcRenderer.invoke('updates:download'),
    install: () => ipcRenderer.invoke('updates:install'),
    onStatus: (callback) => {
      const listener = (_event, status) => callback(status);
      ipcRenderer.on('update-status', listener);
      return () => ipcRenderer.removeListener('update-status', listener);
    }
  },
  pptOutputs: {
    list: () => ipcRenderer.invoke('ppt:list'),
    open: (fileName) => ipcRenderer.invoke('ppt:open', fileName),
    reveal: (fileName) => ipcRenderer.invoke('ppt:reveal', fileName),
    delete: (fileName) => ipcRenderer.invoke('ppt:delete', fileName)
  },
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (patch) => ipcRenderer.invoke('settings:set', patch)
  },
  onLog: (callback) => {
    const listener = (_event, line) => callback(line);
    ipcRenderer.on('runtime-log', listener);
    return () => ipcRenderer.removeListener('runtime-log', listener);
  }
});

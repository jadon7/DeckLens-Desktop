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
  onLog: (callback) => {
    const listener = (_event, line) => callback(line);
    ipcRenderer.on('runtime-log', listener);
    return () => ipcRenderer.removeListener('runtime-log', listener);
  }
});

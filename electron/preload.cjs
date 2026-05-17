const { contextBridge, ipcRenderer } = require('electron');

window.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('electron-shell', `platform-${process.platform}`);
});

contextBridge.exposeInMainWorld('decklensRuntime', {
  getStatus: () => ipcRenderer.invoke('runtime:get-status'),
  install: () => ipcRenderer.invoke('runtime:install'),
  start: () => ipcRenderer.invoke('runtime:start'),
  onStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('runtime-status', listener);
    return () => ipcRenderer.removeListener('runtime-status', listener);
  },
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
  agentSkills: {
    getStatus: () => ipcRenderer.invoke('agent-skills:get-status'),
    install: () => ipcRenderer.invoke('agent-skills:install'),
    update: () => ipcRenderer.invoke('agent-skills:update')
  },
  windowControls: {
    moveBy: (deltaX, deltaY) => ipcRenderer.send('window:move-by', { deltaX, deltaY })
  },
  onLog: (callback) => {
    const listener = (_event, line) => callback(line);
    ipcRenderer.on('runtime-log', listener);
    return () => ipcRenderer.removeListener('runtime-log', listener);
  }
});

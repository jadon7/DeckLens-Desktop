const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { getAgentSkillStatus, installAgentSkills, updateAgentSkills } = require('../lib/agent-skills.cjs');

const UPDATE_FEED_URL = 'https://updates.dsxzai.com/';

let mainWindow;
let backendProcess;
let backendUrl;
let runtimeInstalling = false;
const setupLog = [];
let updateCheckStarted = false;
let updateCheckSilent = false;
let updateErrorSuppressedUntil = 0;
const updateState = {
  status: 'idle',
  message: '检查更新',
  version: app.getVersion(),
  availableVersion: null,
  downloaded: false,
  progress: null,
  error: null
};

autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;
autoUpdater.setFeedURL({
  provider: 'generic',
  url: UPDATE_FEED_URL
});

function publishUpdateState(patch = {}) {
  Object.assign(updateState, patch);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('update-status', { ...updateState });
  }
  return { ...updateState };
}

function updateErrorState(error, fallbackMessage) {
  const message = [
    error?.message,
    error?.name,
    error?.code,
    error?.statusCode,
    error?.stack,
    String(error || '')
  ]
    .filter(Boolean)
    .join(' ');
  const noFeed = [
    '404',
    'Not Found',
    'Cannot find channel',
    'Cannot find',
    'app-update.yml',
    'latest',
    'ENOTFOUND',
    'getaddrinfo',
    'ERR_NAME_NOT_RESOLVED'
  ].some((needle) => message.includes(needle));
  return {
    status: noFeed ? 'not-available' : 'error',
    message: noFeed ? '暂无可用更新' : fallbackMessage,
    error: message,
    progress: null
  };
}

function configureAutoUpdater() {
  autoUpdater.on('checking-for-update', () => {
    if (updateCheckSilent || Date.now() < updateErrorSuppressedUntil) {
      return;
    }
    publishUpdateState({ status: 'checking', message: '正在检查更新...', error: null, progress: null });
  });
  autoUpdater.on('update-available', (info) => {
    publishUpdateState({
      status: 'available',
      message: `发现新版本 ${info.version}`,
      availableVersion: info.version,
      downloaded: false,
      progress: null,
      error: null
    });
  });
  autoUpdater.on('update-not-available', () => {
    if (updateCheckSilent || Date.now() < updateErrorSuppressedUntil) {
      publishUpdateState({ status: 'idle', message: '检查更新', error: null, progress: null });
      return;
    }
    publishUpdateState({ status: 'not-available', message: `当前已是最新版本 ${app.getVersion()}`, error: null, progress: null });
  });
  autoUpdater.on('download-progress', (progress) => {
    publishUpdateState({
      status: 'downloading',
      message: `正在下载更新 ${Math.round(progress.percent || 0)}%`,
      progress: {
        percent: progress.percent || 0,
        transferred: progress.transferred || 0,
        total: progress.total || 0
      },
      error: null
    });
  });
  autoUpdater.on('update-downloaded', (info) => {
    publishUpdateState({
      status: 'downloaded',
      message: `版本 ${info.version} 已下载，重启后安装`,
      availableVersion: info.version,
      downloaded: true,
      progress: null,
      error: null
    });
  });
  autoUpdater.on('error', (error) => {
    if (updateCheckSilent || Date.now() < updateErrorSuppressedUntil) {
      publishUpdateState({ status: 'idle', message: '检查更新', error: null, progress: null });
      return;
    }
    publishUpdateState(updateErrorState(error, '更新检查失败'));
  });
}

async function checkForUpdates({ silent = false } = {}) {
  if (!app.isPackaged) {
    return publishUpdateState({
      status: 'disabled',
      message: '开发模式不检查自动更新',
      error: null,
      progress: null
    });
  }
  if (!silent) {
    updateErrorSuppressedUntil = 0;
    publishUpdateState({ status: 'checking', message: '正在检查更新...', error: null, progress: null });
  } else {
    updateErrorSuppressedUntil = Date.now() + 15000;
  }
  updateCheckSilent = silent;
  try {
    await autoUpdater.checkForUpdates();
    return { ...updateState };
  } finally {
    updateCheckSilent = false;
  }
}

function scheduleUpdateCheck() {
  if (updateCheckStarted) {
    return;
  }
  updateCheckStarted = true;
  setTimeout(() => {
    checkForUpdates({ silent: true }).catch(() => {
      publishUpdateState({ status: 'idle', message: '检查更新', error: null, progress: null });
    });
  }, 5000);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 720,
    title: 'DeckLens',
    backgroundColor: '#ffffff',
    ...(process.platform === 'darwin'
      ? {
          titleBarStyle: 'hiddenInset',
          trafficLightPosition: { x: 16, y: 16 }
        }
      : {}),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith('http://127.0.0.1:')) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (backendUrl && url.startsWith(backendUrl)) {
      return;
    }
    if (!url.startsWith('file://')) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  boot();
}

function userPath(...parts) {
  return path.join(app.getPath('userData'), ...parts);
}

function settingsPath() {
  return userPath('settings.json');
}

function readSettings() {
  try {
    const raw = fs.readFileSync(settingsPath(), 'utf8');
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    if (error.code !== 'ENOENT') {
      appendLog(`Settings read failed: ${error.message}`);
    }
    return {};
  }
}

function sanitizeSettingsPatch(patch) {
  if (!patch || typeof patch !== 'object') {
    return {};
  }
  const allowedKeys = new Set(['falApiKey', 'inpaintBackend', 'language', 'firstRunSeen']);
  return Object.fromEntries(
    Object.entries(patch)
      .filter(([key, value]) => allowedKeys.has(key) && (value === null || typeof value === 'string' || typeof value === 'boolean'))
  );
}

function writeSettings(patch) {
  const current = readSettings();
  const cleanPatch = sanitizeSettingsPatch(patch);
  for (const [key, value] of Object.entries(cleanPatch)) {
    if (value === null || value === '') {
      delete current[key];
    } else {
      current[key] = value;
    }
  }
  fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(current, null, 2));
  return current;
}

function backendDir() {
  return userPath('backend');
}

function packagedBackendDir() {
  return path.join(process.resourcesPath, 'backend');
}

function backendSourceDir() {
  const packagedRoot = packagedBackendDir();
  if (app.isPackaged && fs.existsSync(path.join(packagedRoot, 'app.py'))) {
    return packagedRoot;
  }
  return app.getAppPath();
}

function venvDir() {
  return userPath('python-runtime', 'venv');
}

function outputDir() {
  return userPath('data', 'outputs');
}

function resolveOutputPptx(fileName) {
  if (!fileName || typeof fileName !== 'string' || path.basename(fileName) !== fileName) {
    throw new Error('Invalid PPTX file name.');
  }
  const root = path.resolve(outputDir());
  const resolved = path.resolve(root, fileName);
  const insideOutputDir = resolved === root || resolved.startsWith(`${root}${path.sep}`);
  if (!insideOutputDir || path.extname(resolved).toLowerCase() !== '.pptx') {
    throw new Error('PPTX file is outside DeckLens outputs.');
  }
  return resolved;
}

function listGeneratedPptx() {
  const dir = outputDir();
  fs.mkdirSync(dir, { recursive: true });
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && !entry.name.startsWith('~$') && path.extname(entry.name).toLowerCase() === '.pptx')
    .map((entry) => {
      const filePath = path.join(dir, entry.name);
      const stat = fs.statSync(filePath);
      return {
        id: entry.name,
        name: entry.name,
        size: stat.size,
        createdAt: stat.birthtimeMs,
        modifiedAt: stat.mtimeMs
      };
    })
    .sort((a, b) => b.modifiedAt - a.modifiedAt);
}

function venvPython() {
  return process.platform === 'win32'
    ? path.join(venvDir(), 'Scripts', 'python.exe')
    : path.join(venvDir(), 'bin', 'python');
}

function setupMarkerPath() {
  return userPath('python-runtime', 'installed.json');
}

function appendLog(message) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  setupLog.push(line);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('runtime-log', line);
  }
}

function assertBackendSource(sourceRoot) {
  const requiredEntries = [
    'app.py',
    'engine.py',
    'requirements.txt',
    path.join('templates', 'index.html'),
    'static',
    'font_matcher'
  ];
  const missing = requiredEntries.filter((entry) => !fs.existsSync(path.join(sourceRoot, entry)));
  if (missing.length > 0) {
    throw new Error(`Backend resources are missing from ${sourceRoot}: ${missing.join(', ')}`);
  }
}

function copyBackendSource() {
  const sourceRoot = backendSourceDir();
  assertBackendSource(sourceRoot);

  const targetRoot = backendDir();
  fs.mkdirSync(targetRoot, { recursive: true });

  const entries = ['app.py', 'engine.py', 'requirements.txt', 'templates', 'static', 'font_matcher'];
  for (const entry of entries) {
    const from = path.join(sourceRoot, entry);
    const to = path.join(targetRoot, entry);
    if (!fs.existsSync(from)) {
      continue;
    }
    fs.rmSync(to, { recursive: true, force: true });
    fs.cpSync(from, to, {
      recursive: true,
      filter: (src) => !src.includes('__pycache__') && !src.endsWith('.pyc')
    });
  }
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.DECKLENS_PYTHON) {
    candidates.push({ cmd: process.env.DECKLENS_PYTHON, args: [] });
  }
  if (process.platform === 'win32') {
    candidates.push({ cmd: 'py', args: ['-3.12'] });
    candidates.push({ cmd: 'py', args: ['-3.11'] });
    candidates.push({ cmd: 'py', args: ['-3'] });
    candidates.push({ cmd: 'python', args: [] });
  } else if (process.platform === 'darwin') {
    const macPythonRoots = [
      path.join(os.homedir(), '.local', 'bin'),
      '/opt/homebrew/bin',
      '/usr/local/bin',
      '/Library/Frameworks/Python.framework/Versions/3.12/bin',
      '/Library/Frameworks/Python.framework/Versions/3.11/bin'
    ];
    for (const root of macPythonRoots) {
      candidates.push({ cmd: path.join(root, 'python3.12'), args: [] });
      candidates.push({ cmd: path.join(root, 'python3.11'), args: [] });
    }
    candidates.push({ cmd: 'python3.12', args: [] });
    candidates.push({ cmd: 'python3.11', args: [] });
    candidates.push({ cmd: 'python3', args: [] });
    candidates.push({ cmd: 'python', args: [] });
  } else {
    candidates.push({ cmd: 'python3.12', args: [] });
    candidates.push({ cmd: 'python3.11', args: [] });
    candidates.push({ cmd: 'python3', args: [] });
    candidates.push({ cmd: 'python', args: [] });
  }
  return candidates;
}

function parsePythonVersion(output) {
  const match = output.match(/Python\s+(\d+)\.(\d+)\.(\d+)/);
  if (!match) {
    return null;
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    label: `${match[1]}.${match[2]}.${match[3]}`
  };
}

function supportedPythonVersion(version) {
  return version && version.major === 3 && version.minor >= 11 && version.minor <= 12;
}

function findPython() {
  const rejected = [];
  for (const candidate of pythonCandidates()) {
    const result = spawnSync(candidate.cmd, [...candidate.args, '--version'], { encoding: 'utf8' });
    const output = `${result.stdout || ''}${result.stderr || ''}`.trim();
    const version = parsePythonVersion(output);
    if (result.status === 0 && supportedPythonVersion(version)) {
      return candidate;
    }
    if (result.status === 0) {
      rejected.push(`${candidate.cmd} ${candidate.args.join(' ')}: ${output || 'unknown version'}`);
    }
  }
  if (rejected.length > 0) {
    appendLog(`Unsupported Python candidates: ${rejected.join('; ')}`);
  }
  return null;
}

function runCommand(cmd, args, options = {}) {
  return new Promise((resolve, reject) => {
    appendLog(`$ ${cmd} ${args.join(' ')}`);
    const child = spawn(cmd, args, {
      cwd: backendDir(),
      env: process.env,
      shell: false,
      ...options
    });
    child.stdout.on('data', (chunk) => appendLog(chunk.toString().trim()));
    child.stderr.on('data', (chunk) => appendLog(chunk.toString().trim()));
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${cmd} exited with code ${code}`));
      }
    });
  });
}

async function installRuntime() {
  if (runtimeInstalling) {
    return;
  }
  runtimeInstalling = true;
  setupLog.length = 0;

  try {
    copyBackendSource();
    const python = findPython();
    if (!python) {
      throw new Error('Python 3.11 or 3.12 was not found. Install Python 3.12 and restart DeckLens.');
    }

    fs.mkdirSync(path.dirname(venvDir()), { recursive: true });
    await runCommand(python.cmd, [...python.args, '-m', 'venv', venvDir()]);
    await runCommand(venvPython(), ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel']);
    await runCommand(venvPython(), ['-m', 'pip', 'install', '-r', path.join(backendDir(), 'requirements.txt')]);

    fs.writeFileSync(setupMarkerPath(), JSON.stringify({
      installedAt: new Date().toISOString(),
      platform: process.platform,
      arch: process.arch
    }, null, 2));
    appendLog('Runtime installation complete.');
    await startBackendAndLoad();
  } catch (error) {
    appendLog(`Runtime installation failed: ${error.message}`);
    throw error;
  } finally {
    runtimeInstalling = false;
  }
}

function runtimeInstalled() {
  return fs.existsSync(venvPython()) && fs.existsSync(setupMarkerPath());
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
    server.on('error', reject);
  });
}

function waitForHealth(url, timeoutMs = 60000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      const request = http.get(`${url}/healthz`, (response) => {
        response.resume();
        if (response.statusCode === 200) {
          resolve();
        } else if (Date.now() - started > timeoutMs) {
          reject(new Error(`Backend health check failed with ${response.statusCode}`));
        } else {
          setTimeout(poll, 500);
        }
      });
      request.on('error', () => {
        if (Date.now() - started > timeoutMs) {
          reject(new Error('Backend did not become ready in time.'));
        } else {
          setTimeout(poll, 500);
        }
      });
      request.setTimeout(1000, () => request.destroy());
    };
    poll();
  });
}

async function startBackendAndLoad() {
  if (backendProcess && backendUrl) {
    await mainWindow.loadURL(backendUrl);
    return;
  }
  if (!runtimeInstalled()) {
    await mainWindow.loadFile(path.join(__dirname, 'setup.html'));
    return;
  }

  copyBackendSource();
  const port = await findFreePort();
  backendUrl = `http://127.0.0.1:${port}`;
  const dataDir = userPath('data');
  fs.mkdirSync(dataDir, { recursive: true });

  backendProcess = spawn(venvPython(), ['-m', 'waitress', `--listen=127.0.0.1:${port}`, 'app:app'], {
    cwd: backendDir(),
    env: {
      ...process.env,
      PORT: String(port),
      DECKLENS_DATA_DIR: dataDir,
      DECKLENS_DEVICE: process.env.DECKLENS_DEVICE || 'cpu',
      DECKLENS_INPAINT_BACKEND: process.env.DECKLENS_INPAINT_BACKEND || 'opencv'
    },
    shell: false
  });

  backendProcess.stdout.on('data', (chunk) => appendLog(chunk.toString().trim()));
  backendProcess.stderr.on('data', (chunk) => appendLog(chunk.toString().trim()));
  backendProcess.on('exit', (code) => {
    appendLog(`Backend exited with code ${code}`);
    backendProcess = undefined;
    backendUrl = undefined;
  });

  await waitForHealth(backendUrl);
  await mainWindow.loadURL(backendUrl);
  scheduleUpdateCheck();
}

async function boot() {
  try {
    await startBackendAndLoad();
  } catch (error) {
    appendLog(`Startup failed: ${error.message}`);
    await mainWindow.loadFile(path.join(__dirname, 'setup.html'));
  }
}

ipcMain.handle('runtime:get-status', () => ({
  installed: runtimeInstalled(),
  installing: runtimeInstalling,
  backendUrl,
  userData: app.getPath('userData'),
  platform: process.platform,
  arch: process.arch,
  log: setupLog
}));

ipcMain.handle('runtime:install', async () => {
  await installRuntime();
  return { ok: true };
});

ipcMain.handle('runtime:start', async () => {
  await startBackendAndLoad();
  return { ok: true };
});

ipcMain.handle('updates:get-status', () => ({ ...updateState }));

ipcMain.handle('updates:check', async () => {
  try {
    return await checkForUpdates({ silent: false });
  } catch (error) {
    return publishUpdateState(updateErrorState(error, '更新检查失败'));
  }
});

ipcMain.handle('updates:download', async () => {
  if (!app.isPackaged) {
    return publishUpdateState({ status: 'disabled', message: '开发模式不下载自动更新' });
  }
  publishUpdateState({ status: 'downloading', message: '正在下载更新...', progress: null, error: null });
  try {
    await autoUpdater.downloadUpdate();
    return { ...updateState };
  } catch (error) {
    return publishUpdateState(updateErrorState(error, '更新下载失败'));
  }
});

ipcMain.handle('updates:install', () => {
  if (updateState.status !== 'downloaded') {
    return { ...updateState };
  }
  autoUpdater.quitAndInstall(false, true);
  return { ...updateState };
});

ipcMain.handle('settings:get', () => readSettings());

ipcMain.handle('settings:set', (_event, patch) => writeSettings(patch));

function agentSkillOptions() {
  return {
    appPath: app.getAppPath(),
    resourcesPath: process.resourcesPath,
    isPackaged: app.isPackaged,
    appVersion: app.getVersion()
  };
}

ipcMain.handle('agent-skills:get-status', () => getAgentSkillStatus(agentSkillOptions()));

ipcMain.handle('agent-skills:install', () => installAgentSkills(agentSkillOptions()));

ipcMain.handle('agent-skills:update', () => updateAgentSkills(agentSkillOptions()));

ipcMain.on('window:move-by', (event, delta) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win || win.isDestroyed() || win.isFullScreen()) {
    return;
  }
  const deltaX = Number(delta?.deltaX || 0);
  const deltaY = Number(delta?.deltaY || 0);
  if (!Number.isFinite(deltaX) || !Number.isFinite(deltaY)) {
    return;
  }
  if (Math.abs(deltaX) > 200 || Math.abs(deltaY) > 200) {
    return;
  }
  const [x, y] = win.getPosition();
  win.setPosition(Math.round(x + deltaX), Math.round(y + deltaY), false);
});

ipcMain.handle('ppt:list', () => listGeneratedPptx());

ipcMain.handle('ppt:open', async (_event, fileName) => {
  const pptxPath = resolveOutputPptx(fileName);
  if (!fs.existsSync(pptxPath)) {
    throw new Error('PPTX file no longer exists.');
  }
  const error = await shell.openPath(pptxPath);
  if (error) {
    throw new Error(error);
  }
  return { ok: true };
});

ipcMain.handle('ppt:reveal', (_event, fileName) => {
  const pptxPath = resolveOutputPptx(fileName);
  if (!fs.existsSync(pptxPath)) {
    throw new Error('PPTX file no longer exists.');
  }
  shell.showItemInFolder(pptxPath);
  return { ok: true };
});

ipcMain.handle('ppt:delete', (_event, fileName) => {
  const pptxPath = resolveOutputPptx(fileName);
  if (!fs.existsSync(pptxPath)) {
    return { ok: true };
  }
  fs.rmSync(pptxPath, { force: true });
  return { ok: true };
});

configureAutoUpdater();

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});

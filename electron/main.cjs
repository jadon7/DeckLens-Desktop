const { app, BrowserWindow, ipcMain, shell, Menu } = require('electron');
const { autoUpdater } = require('electron-updater');
const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

function loadAgentSkillRuntime() {
  const candidates = [
    path.join(process.resourcesPath || '', 'cli', 'agent-skills.cjs'),
    path.join(__dirname, '..', 'lib', 'agent-skills.cjs')
  ];
  const runtimePath = candidates.find((candidate) => candidate && fs.existsSync(candidate));
  if (!runtimePath) {
    throw new Error(`Cannot find agent skill runtime. Checked: ${candidates.join(', ')}`);
  }
  return require(runtimePath);
}

const { getAgentSkillStatus, installAgentSkills, updateAgentSkills } = loadAgentSkillRuntime();

const UPDATE_FEED_URL = 'https://updates.dsxzai.com/';
const WINDOWS_PINNED_PADDLE_VERSION = '3.2.2';
const WINDOWS_MANAGED_PYTHON_VERSION = '3.12.10';
const WINDOWS_MANAGED_PYTHON_SHA256 = '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb';
const MAC_MANAGED_PYTHON_VERSION = '3.12.13';
const MAC_MANAGED_PYTHON_BUILD = '20260510';
const MAC_MANAGED_PYTHON_SHA256 = {
  arm64: '5a30271f8d345a5b02b0c9e4e31e0f1e1455a8e4a04fba95cd9762472abc3b17',
  x64: 'cd369e76973c3179bc578230d8615ab621968ed758c5e32f636eecef4ad79894'
};
const WINDOWS_BLOCKED_RUNTIME_PACKAGES = [
  'torch',
  'torchvision',
  'torchaudio',
  'ultralytics',
  'simple-lama-inpainting',
  'segment-anything'
];
let mainWindow;
let backendProcess;
let backendUrl;
let runtimeInstalling = false;
const setupLog = [];
const runtimeState = {
  status: 'idle',
  message: '准备本地运行环境',
  progress: 0,
  error: null
};
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

function publishRuntimeState(patch = {}) {
  Object.assign(runtimeState, patch);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('runtime-status', { ...runtimeState });
  }
  return { ...runtimeState };
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
  Menu.setApplicationMenu(null);

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 720,
    title: 'DeckLens',
    backgroundColor: '#ffffff',
    autoHideMenuBar: true,
    ...(process.platform === 'darwin'
      ? {
          titleBarStyle: 'hiddenInset',
          trafficLightPosition: { x: 16, y: 16 }
        }
      : process.platform === 'win32'
      ? {
          titleBarStyle: 'hidden',
          titleBarOverlay: {
            color: '#ffffff',
            symbolColor: '#111111',
            height: 42
          }
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
  autoInstallAgentSkills();
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

function managedWindowsPythonDir() {
  return userPath('python-runtime', `python-${WINDOWS_MANAGED_PYTHON_VERSION}`);
}

function managedWindowsPython() {
  return path.join(managedWindowsPythonDir(), 'python.exe');
}

function pythonInstallerCachePath() {
  return userPath('python-runtime', 'downloads', `python-${WINDOWS_MANAGED_PYTHON_VERSION}-amd64.exe`);
}

function macPythonRuntimeArch() {
  return process.arch === 'arm64' ? 'aarch64' : 'x86_64';
}

function macPythonArchKey() {
  return process.arch === 'arm64' ? 'arm64' : 'x64';
}

function macPythonArchiveName() {
  return `cpython-${MAC_MANAGED_PYTHON_VERSION}-${MAC_MANAGED_PYTHON_BUILD}-${macPythonRuntimeArch()}-apple-darwin-install_only.tar.gz`;
}

function managedMacPythonDir() {
  return userPath('python-runtime', `cpython-${MAC_MANAGED_PYTHON_VERSION}-${MAC_MANAGED_PYTHON_BUILD}-${macPythonRuntimeArch()}`);
}

function managedMacPython() {
  return path.join(managedMacPythonDir(), 'python', 'bin', 'python3.12');
}

function macPythonArchiveCachePath() {
  return userPath('python-runtime', 'downloads', macPythonArchiveName());
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

function windowsRuntimeSanitizedMarkerPath() {
  return userPath('python-runtime', 'windows-no-torch-v1.json');
}

function windowsPaddlePinnedMarkerPath() {
  return userPath('python-runtime', 'windows-paddle-3.2.2.json');
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

function runtimeRequirementsPath() {
  const requirementsPath = path.join(backendDir(), 'requirements.txt');
  if (process.platform !== 'win32') {
    return requirementsPath;
  }
  const excluded = /^(torch|torchvision|torchaudio|ultralytics|simple-lama-inpainting|segment-anything|paddlepaddle)([<>=~! ].*)?$/i;
  const source = fs.readFileSync(requirementsPath, 'utf8');
  const lines = source
    .split(/\r?\n/)
    .filter((line) => !excluded.test(line.trim()))
    .filter((line) => line.trim() !== '');
  lines.push('paddlepaddle==3.2.2');
  const windowsRequirementsPath = path.join(backendDir(), 'requirements-windows.txt');
  fs.writeFileSync(windowsRequirementsPath, `${lines.join('\n')}\n`);
  return windowsRequirementsPath;
}

function installedPaddleVersion() {
  if (process.platform !== 'win32' || !fs.existsSync(venvPython())) {
    return null;
  }
  const result = spawnSync(venvPython(), ['-c', 'import importlib.metadata as m; print(m.version("paddlepaddle"))'], {
    cwd: backendDir(),
    env: process.env,
    encoding: 'utf8'
  });
  if (result.status !== 0) {
    return null;
  }
  const output = `${result.stdout || ''}${result.stderr || ''}`;
  const match = output.match(/\b\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)?\b/);
  return match ? match[0] : null;
}

function installedWindowsBlockedRuntimePackages() {
  if (process.platform !== 'win32' || !fs.existsSync(venvPython())) {
    return [];
  }
  const probe = spawnSync(venvPython(), [
    '-c',
    `import importlib.metadata as m
blocked = ${JSON.stringify(WINDOWS_BLOCKED_RUNTIME_PACKAGES)}
installed = []
for pkg in blocked:
    try:
        m.version(pkg)
        installed.append(pkg)
    except m.PackageNotFoundError:
        pass
print("\\n".join(installed))`
  ], {
    cwd: backendDir(),
    env: process.env,
    encoding: 'utf8'
  });
  if (probe.status !== 0) {
    return [];
  }
  return (probe.stdout || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function windowsRuntimeRepairStatus() {
  if (process.platform !== 'win32' || !runtimeInstalled()) {
    return {
      needed: false,
      paddleVersion: null,
      blockedPackages: []
    };
  }
  const paddleVersion = installedPaddleVersion();
  const blockedPackages = installedWindowsBlockedRuntimePackages();
  return {
    needed: paddleVersion !== WINDOWS_PINNED_PADDLE_VERSION || blockedPackages.length > 0,
    paddleVersion,
    blockedPackages
  };
}

async function ensureWindowsPaddleRuntime({ showProgress = false } = {}) {
  if (process.platform !== 'win32' || !fs.existsSync(venvPython())) {
    return;
  }
  const requiredVersion = WINDOWS_PINNED_PADDLE_VERSION;
  const currentVersion = installedPaddleVersion();
  if (currentVersion === requiredVersion && fs.existsSync(windowsPaddlePinnedMarkerPath())) {
    return;
  }
  if (currentVersion !== requiredVersion) {
    if (showProgress) {
      publishRuntimeState({
        status: 'repairing',
        message: '正在升级 Windows 图像识别运行环境...',
        progress: 52,
        error: null
      });
    }
    appendLog(`Pinning Windows paddlepaddle runtime: ${currentVersion || 'missing'} -> ${requiredVersion}`);
    await runCommand(venvPython(), ['-m', 'pip', 'install', `paddlepaddle==${requiredVersion}`]);
  }
  fs.writeFileSync(windowsPaddlePinnedMarkerPath(), JSON.stringify({
    pinnedAt: new Date().toISOString(),
    package: 'paddlepaddle',
    version: requiredVersion,
    reason: 'Avoid Paddle 3.3.x oneDNN/PIR OCR failures on Windows.'
  }, null, 2));
}

async function sanitizeWindowsRuntime({ showProgress = false } = {}) {
  if (process.platform !== 'win32' || !fs.existsSync(venvPython())) {
    return;
  }
  const installed = installedWindowsBlockedRuntimePackages();
  if (installed.length === 0 && fs.existsSync(windowsRuntimeSanitizedMarkerPath())) {
    return;
  }
  if (installed.length > 0 && showProgress) {
    publishRuntimeState({
      status: 'repairing',
      message: '正在清理 Windows 兼容性依赖...',
      progress: 34,
      error: null
    });
  }
  appendLog('Removing torch-backed optional packages from the Windows runtime...');
  try {
    await runCommand(venvPython(), ['-m', 'pip', 'uninstall', '-y', ...WINDOWS_BLOCKED_RUNTIME_PACKAGES]);
  } catch (error) {
    appendLog(`Windows runtime optional package cleanup skipped: ${error.message}`);
  }
  fs.writeFileSync(windowsRuntimeSanitizedMarkerPath(), JSON.stringify({
    sanitizedAt: new Date().toISOString(),
    reason: 'Avoid torch c10.dll initialization failures on Windows.'
  }, null, 2));
}

async function repairWindowsRuntimeIfNeeded({ showProgress = false } = {}) {
  const repairStatus = windowsRuntimeRepairStatus();
  if (!repairStatus.needed) {
    return false;
  }
  if (showProgress) {
    setupLog.length = 0;
    publishRuntimeState({
      status: 'repairing',
      message: '正在升级 DeckLens 运行环境...',
      progress: 18,
      error: null
    });
  }
  await sanitizeWindowsRuntime({ showProgress });
  await ensureWindowsPaddleRuntime({ showProgress });
  if (showProgress) {
    publishRuntimeState({
      status: 'starting',
      message: '运行环境升级完成，正在进入 DeckLens...',
      progress: 94,
      error: null
    });
  }
  return true;
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.DECKLENS_PYTHON) {
    candidates.push({ cmd: process.env.DECKLENS_PYTHON, args: [] });
  }
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA;
    const windowsRoot = process.env.SystemRoot || 'C:\\Windows';
    const programFiles = [process.env.ProgramFiles, process.env['ProgramFiles(x86)']].filter(Boolean);
    candidates.push({ cmd: managedWindowsPython(), args: [] });
    candidates.push({ cmd: 'py', args: ['-3.12'] });
    candidates.push({ cmd: 'py', args: ['-3.11'] });
    candidates.push({ cmd: 'py', args: ['-3'] });
    candidates.push({ cmd: path.join(windowsRoot, 'py.exe'), args: ['-3.12'] });
    candidates.push({ cmd: path.join(windowsRoot, 'py.exe'), args: ['-3.11'] });
    if (localAppData) {
      candidates.push({ cmd: path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'), args: [] });
      candidates.push({ cmd: path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'), args: [] });
      candidates.push({ cmd: path.join(localAppData, 'Microsoft', 'WindowsApps', 'python3.12.exe'), args: [] });
      candidates.push({ cmd: path.join(localAppData, 'Microsoft', 'WindowsApps', 'python3.11.exe'), args: [] });
      candidates.push({ cmd: path.join(localAppData, 'Microsoft', 'WindowsApps', 'python.exe'), args: [] });
      candidates.push(...pythonCandidatesFromDirectory(path.join(localAppData, 'Programs', 'Python')));
    }
    for (const root of programFiles) {
      candidates.push({ cmd: path.join(root, 'Python312', 'python.exe'), args: [] });
      candidates.push({ cmd: path.join(root, 'Python311', 'python.exe'), args: [] });
      candidates.push(...pythonCandidatesFromDirectory(root));
    }
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
    candidates.push({ cmd: managedMacPython(), args: [] });
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

function pythonCandidatesFromDirectory(root) {
  const candidates = [];
  try {
    for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
      if (!entry.isDirectory() || !/^Python3(11|12)/i.test(entry.name)) {
        continue;
      }
      candidates.push({ cmd: path.join(root, entry.name, 'python.exe'), args: [] });
    }
  } catch {
    // Some Windows locations, especially WindowsApps, are not listable by normal apps.
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

async function installWindowsPython() {
  if (process.platform !== 'win32') {
    return false;
  }

  const wingetPath = findWinget();
  if (!wingetPath) {
    appendLog('Windows package manager winget was not found.');
    return false;
  }

  const winget = spawnSync(wingetPath, ['--version'], { encoding: 'utf8' });
  if (winget.status !== 0) {
    appendLog('Windows package manager winget was not found.');
    return false;
  }

  publishRuntimeState({
    status: 'installing',
    message: '正在准备 Python 3.12...',
    progress: 22,
    error: null
  });
  appendLog('Python 3.12 was not found. Installing Python 3.12 with winget...');
  await runCommand(wingetPath, [
    'install',
    '-e',
    '--id',
    'Python.Python.3.12',
    '--source',
    'winget',
    '--scope',
    'user',
    '--disable-interactivity',
    '--accept-package-agreements',
    '--accept-source-agreements'
  ], { cwd: app.getPath('userData') });

  publishRuntimeState({
    status: 'installing',
    message: '正在确认 Python 运行环境...',
    progress: 36,
    error: null
  });
  appendLog('Python installer finished. Checking Python again...');
  return true;
}

function findWinget() {
  if (process.platform !== 'win32') {
    return null;
  }
  const localAppData = process.env.LOCALAPPDATA;
  const candidates = [
    'winget',
    localAppData ? path.join(localAppData, 'Microsoft', 'WindowsApps', 'winget.exe') : null
  ].filter(Boolean);
  for (const candidate of candidates) {
    const probe = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
    if (probe.status === 0) {
      return candidate;
    }
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

function requestModuleForUrl(url) {
  return url.startsWith('https:') ? https : http;
}

function fileSha256(filePath) {
  const hash = require('node:crypto').createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function downloadFile(url, destination, redirectCount = 0) {
  return new Promise((resolve, reject) => {
    if (redirectCount > 5) {
      reject(new Error(`Too many redirects while downloading ${url}`));
      return;
    }

    fs.mkdirSync(path.dirname(destination), { recursive: true });
    const request = requestModuleForUrl(url).get(url, (response) => {
      const status = response.statusCode || 0;
      if (status >= 300 && status < 400 && response.headers.location) {
        response.resume();
        const nextUrl = new URL(response.headers.location, url).toString();
        downloadFile(nextUrl, destination, redirectCount + 1).then(resolve, reject);
        return;
      }
      if (status < 200 || status >= 300) {
        response.resume();
        reject(new Error(`Download failed with HTTP ${status}: ${url}`));
        return;
      }

      const tempPath = `${destination}.download`;
      const file = fs.createWriteStream(tempPath);
      response.pipe(file);
      file.on('finish', () => {
        file.close(() => {
          fs.renameSync(tempPath, destination);
          resolve(destination);
        });
      });
      file.on('error', (error) => {
        fs.rmSync(tempPath, { force: true });
        reject(error);
      });
    });
    request.on('error', reject);
    request.setTimeout(120000, () => request.destroy(new Error(`Download timed out: ${url}`)));
  });
}

async function waitForFile(filePath, timeoutMs = 90000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (fs.existsSync(filePath)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return fs.existsSync(filePath);
}

async function installManagedWindowsPython() {
  if (process.platform !== 'win32') {
    return false;
  }
  if (fs.existsSync(managedWindowsPython())) {
    return true;
  }

  const installerPath = pythonInstallerCachePath();
  const urls = [
    `${UPDATE_FEED_URL}runtime/python-${WINDOWS_MANAGED_PYTHON_VERSION}-amd64.exe`,
    `https://www.python.org/ftp/python/${WINDOWS_MANAGED_PYTHON_VERSION}/python-${WINDOWS_MANAGED_PYTHON_VERSION}-amd64.exe`
  ];

  publishRuntimeState({
    status: 'installing',
    message: '正在下载 DeckLens 内置 Python 运行环境...',
    progress: 22,
    error: null
  });

  let lastDownloadError = null;
  for (const url of urls) {
    try {
      appendLog(`Downloading managed Python ${WINDOWS_MANAGED_PYTHON_VERSION} from ${url}`);
      if (!fs.existsSync(installerPath) || fs.statSync(installerPath).size < 1024 * 1024) {
        await downloadFile(url, installerPath);
      }
      const digest = fileSha256(installerPath);
      if (digest !== WINDOWS_MANAGED_PYTHON_SHA256) {
        throw new Error(`Managed Python checksum mismatch: ${digest}`);
      }
      lastDownloadError = null;
      break;
    } catch (error) {
      lastDownloadError = error;
      appendLog(`Managed Python download failed: ${error.message}`);
      fs.rmSync(installerPath, { force: true });
    }
  }
  if (lastDownloadError) {
    throw lastDownloadError;
  }

  publishRuntimeState({
    status: 'installing',
    message: '正在安装 DeckLens 内置 Python 运行环境...',
    progress: 30,
    error: null
  });

  fs.rmSync(managedWindowsPythonDir(), { recursive: true, force: true });
  fs.mkdirSync(managedWindowsPythonDir(), { recursive: true });
  await runCommand(installerPath, [
    '/quiet',
    'InstallAllUsers=0',
    `TargetDir=${managedWindowsPythonDir()}`,
    'Include_launcher=0',
    'Include_pip=1',
    'Include_test=0',
    'PrependPath=0',
    'Shortcuts=0'
  ], { cwd: app.getPath('userData') });

  const installed = await waitForFile(managedWindowsPython());
  if (!installed) {
    throw new Error('Managed Python installer finished but python.exe was not created.');
  }
  appendLog(`Managed Python installed at ${managedWindowsPython()}`);
  return true;
}

async function installManagedMacPython() {
  if (process.platform !== 'darwin') {
    return false;
  }
  if (fs.existsSync(managedMacPython())) {
    return true;
  }

  const archivePath = macPythonArchiveCachePath();
  const archiveName = macPythonArchiveName();
  const encodedUpstreamName = `cpython-${MAC_MANAGED_PYTHON_VERSION}%2B${MAC_MANAGED_PYTHON_BUILD}-${macPythonRuntimeArch()}-apple-darwin-install_only.tar.gz`;
  const urls = [
    `${UPDATE_FEED_URL}runtime/${archiveName}`,
    `https://github.com/astral-sh/python-build-standalone/releases/download/${MAC_MANAGED_PYTHON_BUILD}/${encodedUpstreamName}`
  ];

  publishRuntimeState({
    status: 'installing',
    message: '正在下载 DeckLens 内置 Python 运行环境...',
    progress: 22,
    error: null
  });

  let lastDownloadError = null;
  for (const url of urls) {
    try {
      appendLog(`Downloading managed macOS Python ${MAC_MANAGED_PYTHON_VERSION} from ${url}`);
      if (!fs.existsSync(archivePath) || fs.statSync(archivePath).size < 1024 * 1024) {
        await downloadFile(url, archivePath);
      }
      const digest = fileSha256(archivePath);
      const expectedDigest = MAC_MANAGED_PYTHON_SHA256[macPythonArchKey()];
      if (digest !== expectedDigest) {
        throw new Error(`Managed macOS Python checksum mismatch: ${digest}`);
      }
      lastDownloadError = null;
      break;
    } catch (error) {
      lastDownloadError = error;
      appendLog(`Managed macOS Python download failed: ${error.message}`);
      fs.rmSync(archivePath, { force: true });
    }
  }
  if (lastDownloadError) {
    throw lastDownloadError;
  }

  publishRuntimeState({
    status: 'installing',
    message: '正在安装 DeckLens 内置 Python 运行环境...',
    progress: 30,
    error: null
  });

  fs.rmSync(managedMacPythonDir(), { recursive: true, force: true });
  fs.mkdirSync(managedMacPythonDir(), { recursive: true });
  await runCommand('/usr/bin/tar', ['-xzf', archivePath, '-C', managedMacPythonDir()], {
    cwd: app.getPath('userData')
  });

  const installed = await waitForFile(managedMacPython());
  if (!installed) {
    throw new Error('Managed macOS Python archive extracted but python3.12 was not created.');
  }
  appendLog(`Managed macOS Python installed at ${managedMacPython()}`);
  return true;
}

async function installRuntime() {
  if (runtimeInstalling) {
    return;
  }
  runtimeInstalling = true;
  setupLog.length = 0;
  publishRuntimeState({
    status: 'installing',
    message: '正在准备 DeckLens 运行环境...',
    progress: 6,
    error: null
  });

  try {
    copyBackendSource();
    publishRuntimeState({
      status: 'installing',
      message: '正在检查 Python 运行环境...',
      progress: 14,
      error: null
    });
    let python = findPython();
    if (!python && process.platform === 'win32') {
      try {
        await installManagedWindowsPython();
      } catch (error) {
        appendLog(`Managed Python install failed, falling back to winget: ${error.message}`);
        try {
          await installWindowsPython();
        } catch (wingetError) {
          appendLog(`winget Python install failed: ${wingetError.message}`);
        }
      }
      python = findPython();
    }
    if (!python && process.platform === 'darwin') {
      await installManagedMacPython();
      python = findPython();
    }
    if (!python) {
      throw new Error('DeckLens could not prepare Python 3.11/3.12 automatically. Check the network and retry.');
    }

    fs.mkdirSync(path.dirname(venvDir()), { recursive: true });
    publishRuntimeState({
      status: 'installing',
      message: '正在创建本地运行环境...',
      progress: 42,
      error: null
    });
    await runCommand(python.cmd, [...python.args, '-m', 'venv', venvDir()]);
    publishRuntimeState({
      status: 'installing',
      message: '正在准备基础依赖...',
      progress: 58,
      error: null
    });
    await runCommand(venvPython(), ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel']);
    publishRuntimeState({
      status: 'installing',
      message: '正在安装图像识别与 PPTX 生成依赖...',
      progress: 72,
      error: null
    });
    await runCommand(venvPython(), ['-m', 'pip', 'install', '-r', runtimeRequirementsPath()]);
    await sanitizeWindowsRuntime({ showProgress: false });
    await ensureWindowsPaddleRuntime({ showProgress: false });

    fs.writeFileSync(setupMarkerPath(), JSON.stringify({
      installedAt: new Date().toISOString(),
      platform: process.platform,
      arch: process.arch
    }, null, 2));
    publishRuntimeState({
      status: 'starting',
      message: '依赖安装完成，正在进入 DeckLens...',
      progress: 96,
      error: null
    });
    appendLog('Runtime installation complete.');
    await startBackendAndLoad();
  } catch (error) {
    publishRuntimeState({
      status: 'error',
      message: '运行环境准备失败',
      progress: 0,
      error: error.message
    });
    appendLog(`Runtime installation failed: ${error.message}`);
    throw error;
  } finally {
    runtimeInstalling = false;
    if (runtimeState.status === 'installing') {
      publishRuntimeState({ status: 'idle' });
    }
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
  if (process.platform === 'win32' && windowsRuntimeRepairStatus().needed) {
    await mainWindow.loadFile(path.join(__dirname, 'setup.html'));
  }
  const repaired = await repairWindowsRuntimeIfNeeded({ showProgress: true });
  if (repaired && mainWindow && !mainWindow.isDestroyed()) {
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
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
      DECKLENS_INPAINT_BACKEND: process.env.DECKLENS_INPAINT_BACKEND || (process.platform === 'win32' ? 'local_mean' : 'lama'),
      DECKLENS_SEGMENT_BACKEND: process.env.DECKLENS_SEGMENT_BACKEND || (process.platform === 'win32' ? 'opencv' : 'fastsam'),
      DECKLENS_DISABLE_TORCH: process.env.DECKLENS_DISABLE_TORCH || (process.platform === 'win32' ? '1' : '0'),
      DECKLENS_KEEP_OCR_MODEL: process.env.DECKLENS_KEEP_OCR_MODEL || (process.platform === 'win32' ? '1' : '0')
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
  runtime: { ...runtimeState },
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
  autoUpdater.quitAndInstall(process.platform === 'win32', true);
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

let agentSkillAutoInstallStarted = false;

function autoInstallAgentSkills() {
  if (agentSkillAutoInstallStarted) {
    return;
  }
  agentSkillAutoInstallStarted = true;
  setTimeout(() => {
    try {
      const status = getAgentSkillStatus(agentSkillOptions());
      const visibleTargets = status?.visibleTargets || status?.targets?.filter((target) => target.detected || target.installed) || [];
      if (!status?.sourceAvailable || visibleTargets.length === 0) {
        return;
      }
      const needsUpdate = (status.updateAvailableCount || 0) > 0;
      const needsInstall = (status.installedCount || 0) === 0;
      if (!needsUpdate && !needsInstall) {
        return;
      }
      const result = needsUpdate ? updateAgentSkills(agentSkillOptions()) : installAgentSkills(agentSkillOptions());
      appendLog(`Agent Skill auto-sync complete: ${result.installed?.length || 0} installed, ${result.skipped?.length || 0} skipped, ${result.failed?.length || 0} failed.`);
    } catch (error) {
      appendLog(`Agent Skill auto-sync failed: ${error.message}`);
    }
  }, 1500);
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

#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT_DIR = path.resolve(__dirname, '..');

function printHelp() {
  console.log(`DeckLens CLI

Usage:
  decklens convert <input...> [options]
  decklens icons find <name> [options]
  decklens icons libraries [options]
  decklens install-skills [options]
  decklens skills status [options]
  decklens skills update [options]
  decklens --help

Commands:
  convert    Convert image-like presentation pages into an editable PPTX deck.
  icons      Find bundled icon assets for Agent PPT post-processing.
  install-skills
             Install the DeckLens Agent skill into user-global Agent skill folders.
  skills     Inspect or update installed DeckLens Agent skills.

Convert options are passed through to DeckLens' conversion engine:
  --output <file>             Output .pptx path
  --output-dir <directory>    Output directory when --output is omitted
  --mode <standard|element|ai>
  --inpaint-backend <lama|local_mean>
  --qwen-layers <3-8>
  --fal-key <key>
  --overwrite
  --json

Install skill options:
  --force                     Overwrite modified DeckLens-managed skills
  --json                      Print machine-readable install status

Icon options:
  --style <outline|solid|filled|regular>
  --json                      Print machine-readable icon matches
`);
}

function userDataDir() {
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'decklens-desktop');
  }
  if (process.platform === 'win32') {
    return path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'decklens-desktop');
  }
  return path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'), 'decklens-desktop');
}

function fileExists(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function backendRootCandidates() {
  return [
    process.env.DECKLENS_BACKEND_DIR,
    path.resolve(ROOT_DIR),
    path.resolve(__dirname, '..', 'backend'),
    path.resolve(process.resourcesPath || '', 'backend'),
    path.resolve(userDataDir(), 'backend'),
    process.cwd()
  ].filter(Boolean);
}

function findBackendRoot() {
  for (const candidate of backendRootCandidates()) {
    const resolved = path.resolve(candidate);
    if (fileExists(path.join(resolved, 'decklens_cli.py')) && fileExists(path.join(resolved, 'engine.py'))) {
      return resolved;
    }
  }
  throw new Error('DeckLens backend was not found. Set DECKLENS_BACKEND_DIR to the backend directory.');
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.DECKLENS_PYTHON) {
    candidates.push({ cmd: process.env.DECKLENS_PYTHON, args: [] });
  }

  const venvRoot = path.join(userDataDir(), 'python-runtime', 'venv');
  if (process.platform === 'win32') {
    candidates.push({ cmd: path.join(venvRoot, 'Scripts', 'python.exe'), args: [] });
    candidates.push({ cmd: 'py', args: ['-3.12'] });
    candidates.push({ cmd: 'py', args: ['-3.11'] });
    candidates.push({ cmd: 'py', args: ['-3'] });
    candidates.push({ cmd: 'python', args: [] });
  } else {
    candidates.push({ cmd: path.join(venvRoot, 'bin', 'python'), args: [] });
    candidates.push({ cmd: '/opt/homebrew/bin/python3.12', args: [] });
    candidates.push({ cmd: '/opt/homebrew/bin/python3.11', args: [] });
    candidates.push({ cmd: '/usr/local/bin/python3.12', args: [] });
    candidates.push({ cmd: '/usr/local/bin/python3.11', args: [] });
    candidates.push({ cmd: 'python3.12', args: [] });
    candidates.push({ cmd: 'python3.11', args: [] });
    candidates.push({ cmd: 'python3', args: [] });
    candidates.push({ cmd: 'python', args: [] });
  }
  return candidates;
}

function parsePythonVersion(output) {
  const match = output.match(/Python\s+(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]) };
}

function supportedPython(version) {
  return version && version.major === 3 && version.minor >= 11 && version.minor <= 12;
}

function findPython() {
  for (const candidate of pythonCandidates()) {
    const result = spawnSync(candidate.cmd, [...candidate.args, '--version'], { encoding: 'utf8' });
    const version = parsePythonVersion(`${result.stdout || ''}${result.stderr || ''}`);
    if (result.status === 0 && supportedPython(version)) {
      return candidate;
    }
  }
  throw new Error('Python 3.11 or 3.12 runtime was not found. Start DeckLens once to install the runtime, or set DECKLENS_PYTHON.');
}

function runConvert(args) {
  const backendRoot = findBackendRoot();
  const python = findPython();
  const script = path.join(backendRoot, 'decklens_cli.py');
  const env = {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH ? `${backendRoot}${path.delimiter}${process.env.PYTHONPATH}` : backendRoot
  };

  const result = spawnSync(python.cmd, [...python.args, script, ...args], {
    cwd: backendRoot,
    env,
    stdio: 'inherit'
  });
  return result.status === null ? 1 : result.status;
}

function normalizeIconName(name) {
  const normalized = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/['"]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  const aliases = {
    email: 'mail',
    envelope: 'mail',
    world: 'globe',
    website: 'globe',
    next: 'arrow-right',
    right: 'arrow-right',
    account: 'user',
    person: 'user',
    tick: 'check',
    confirm: 'check',
    close: 'x',
    delete: 'trash',
    remove: 'trash'
  };
  return aliases[normalized] || normalized;
}

function optionValue(args, name) {
  const index = args.indexOf(name);
  if (index === -1) return null;
  return args[index + 1] || null;
}

function bundledIconRoots() {
  const roots = [
    path.join(__dirname, 'icons'),
    path.join(ROOT_DIR, 'icons'),
    path.join(ROOT_DIR, 'cli', 'icons'),
    path.join(process.resourcesPath || '', 'cli', 'icons')
  ];
  if (process.env.DECKLENS_ICON_DIR) {
    roots.unshift(process.env.DECKLENS_ICON_DIR);
  }
  return roots;
}

function nodeModuleRoots() {
  return [
    path.join(ROOT_DIR, 'node_modules'),
    path.join(process.resourcesPath || '', 'app.asar.unpacked', 'node_modules')
  ];
}

function iconLibraries() {
  const candidates = [];

  function addDirs(library, style, dirs, extension = 'svg') {
    for (const dir of dirs) {
      candidates.push({ library, style, dir, extension });
    }
  }

  const bundledRoots = bundledIconRoots();
  const moduleRoots = nodeModuleRoots();
  addDirs('lucide-static', 'outline', [
    ...bundledRoots.map((root) => path.join(root, 'lucide-static')),
    ...moduleRoots.map((root) => path.join(root, 'lucide-static', 'icons'))
  ]);
  addDirs('tabler-icons', 'outline', [
    ...bundledRoots.map((root) => path.join(root, 'tabler-icons', 'outline')),
    ...moduleRoots.map((root) => path.join(root, '@tabler', 'icons', 'icons', 'outline'))
  ]);
  addDirs('tabler-icons', 'filled', [
    ...bundledRoots.map((root) => path.join(root, 'tabler-icons', 'filled')),
    ...moduleRoots.map((root) => path.join(root, '@tabler', 'icons', 'icons', 'filled'))
  ]);
  addDirs('heroicons', 'outline', [
    ...bundledRoots.map((root) => path.join(root, 'heroicons', '24', 'outline')),
    ...moduleRoots.map((root) => path.join(root, 'heroicons', '24', 'outline'))
  ]);
  addDirs('heroicons', 'solid', [
    ...bundledRoots.map((root) => path.join(root, 'heroicons', '24', 'solid')),
    ...bundledRoots.map((root) => path.join(root, 'heroicons', '20', 'solid')),
    ...bundledRoots.map((root) => path.join(root, 'heroicons', '16', 'solid')),
    ...moduleRoots.map((root) => path.join(root, 'heroicons', '24', 'solid')),
    ...moduleRoots.map((root) => path.join(root, 'heroicons', '20', 'solid')),
    ...moduleRoots.map((root) => path.join(root, 'heroicons', '16', 'solid'))
  ]);
  addDirs('phosphor-icons', 'font', [
    ...bundledRoots.map((root) => path.join(root, 'phosphor-icons', 'fonts')),
    ...moduleRoots.map((root) => path.join(root, 'phosphor-icons', 'src', 'fonts'))
  ], 'font');
  return candidates;
}

function existingIconLibraries() {
  return iconLibraries().filter((library) => {
    try {
      return fs.statSync(library.dir).isDirectory();
    } catch {
      return false;
    }
  });
}

function findIcons(args) {
  const json = args.includes('--json');
  const preferredStyle = optionValue(args, '--style');
  const positional = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--json') continue;
    if (arg === '--style') {
      index += 1;
      continue;
    }
    if (!arg.startsWith('--')) positional.push(arg);
  }
  const name = normalizeIconName(positional[0] || '');
  if (!name) {
    throw new Error('Icon name is required. Example: decklens icons find mail --json');
  }

  const names = [name];
  if (name === 'globe') names.push('globe-2', 'globe-alt', 'globe-americas', 'world');
  if (name === 'mail') names.push('envelope');
  if (name === 'user') names.push('user-circle');

  const matches = [];
  const seenPaths = new Set();
  for (const library of existingIconLibraries()) {
    if (preferredStyle && library.style !== preferredStyle) continue;
    if (library.extension === 'font') {
      continue;
    }
    for (const candidateName of names) {
      const filePath = path.join(library.dir, `${candidateName}.svg`);
      if (fileExists(filePath) && !seenPaths.has(filePath)) {
        seenPaths.add(filePath);
        matches.push({
          library: library.library,
          style: library.style,
          name: candidateName,
          path: filePath
        });
      }
    }
  }

  if (json) {
    console.log(JSON.stringify({ query: name, matches }, null, 2));
  } else if (matches.length) {
    for (const match of matches) {
      console.log(`${match.library}/${match.style}/${match.name}: ${match.path}`);
    }
  } else {
    console.log(`No bundled icon found for "${name}".`);
  }
  return matches.length ? 0 : 1;
}

function listIconLibraries(args) {
  const json = args.includes('--json');
  const libraries = existingIconLibraries().map((library) => ({
    library: library.library,
    style: library.style,
    path: library.dir,
    type: library.extension === 'font' ? 'font' : 'svg'
  }));
  if (json) {
    console.log(JSON.stringify({ libraries }, null, 2));
  } else {
    for (const library of libraries) {
      console.log(`${library.library}/${library.style} (${library.type}): ${library.path}`);
    }
  }
  return 0;
}

function runIcons(args) {
  const subcommand = args[0] || 'libraries';
  if (subcommand === 'find') {
    return findIcons(args.slice(1));
  }
  if (subcommand === 'libraries') {
    return listIconLibraries(args.slice(1));
  }
  console.error(`Unknown icons command: ${subcommand}`);
  printHelp();
  return 1;
}

function loadAgentSkillInstaller() {
  const candidates = [
    path.join(__dirname, 'agent-skills.cjs'),
    path.join(ROOT_DIR, 'lib', 'agent-skills.cjs'),
    path.join(ROOT_DIR, 'electron', 'agent-skills.cjs')
  ];
  for (const candidate of candidates) {
    if (fileExists(candidate)) {
      return require(candidate);
    }
  }
  throw new Error('DeckLens Agent Skill installer was not found.');
}

function skillInstallOptions() {
  return {
    home: process.env.DECKLENS_SKILL_HOME,
    appPath: ROOT_DIR,
    resourcesPath: ROOT_DIR,
    isPackaged: false,
    appVersion: 'cli',
    force: process.argv.includes('--force')
  };
}

function printSkillResult(result, action) {
  const installed = result.installed || [];
  const skipped = result.skipped || [];
  const failed = result.failed || [];
  if (installed.length > 0) {
    console.log(`DeckLens Agent Skill ${action} ${installed.length} location${installed.length === 1 ? '' : 's'}:`);
    for (const target of installed) {
      console.log(`- ${target.name}: ${target.path}`);
    }
  } else {
    console.log(`No Agent skill locations were ${action}.`);
  }
  if (skipped.length > 0) {
    console.log(`Skipped ${skipped.length} location${skipped.length === 1 ? '' : 's'}:`);
    for (const target of skipped) {
      console.log(`- ${target.name}: ${target.reason}`);
    }
  }
  if (failed.length > 0) {
    console.error(`Failed ${failed.length} location${failed.length === 1 ? '' : 's'}:`);
    for (const target of failed) {
      console.error(`- ${target.name}: ${target.error}`);
    }
  }
}

function runInstallSkills(args) {
  const json = args.includes('--json');
  const { installAgentSkills } = loadAgentSkillInstaller();
  const result = installAgentSkills(skillInstallOptions());
  if (json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printSkillResult(result, 'installed to');
  }
  return result.failed?.length ? 1 : 0;
}

function printSkillStatus(result) {
  console.log(`DeckLens Agent Skill source: ${result.sourceVersion || 'unknown'} (${result.sourceAvailable ? 'available' : 'missing'})`);
  for (const target of result.visibleTargets || []) {
    const version = target.skillVersion || 'not installed';
    const state = target.state || (target.installed ? 'installed' : 'not-installed');
    console.log(`- ${target.name}: ${version} · ${state}`);
  }
}

function runSkills(args) {
  const subcommand = args[0] || 'status';
  const json = args.includes('--json');
  const installer = loadAgentSkillInstaller();
  if (subcommand === 'status') {
    const result = installer.getAgentSkillStatus(skillInstallOptions());
    if (json) console.log(JSON.stringify(result, null, 2));
    else printSkillStatus(result);
    return 0;
  }
  if (subcommand === 'update') {
    const result = installer.updateAgentSkills(skillInstallOptions());
    if (json) console.log(JSON.stringify(result, null, 2));
    else printSkillResult(result, 'updated');
    return result.failed?.length ? 1 : 0;
  }
  console.error(`Unknown skills command: ${subcommand}`);
  printHelp();
  return 1;
}

function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  if (!command || command === '--help' || command === '-h') {
    printHelp();
    return 0;
  }

  if (command === 'convert') {
    return runConvert(args.slice(1));
  }

  if (command === 'icons') {
    return runIcons(args.slice(1));
  }

  if (command === 'install-skills') {
    return runInstallSkills(args.slice(1));
  }

  if (command === 'skills') {
    return runSkills(args.slice(1));
  }

  console.error(`Unknown DeckLens command: ${command}`);
  printHelp();
  return 1;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(`DeckLens CLI failed: ${error.message}`);
  process.exitCode = 1;
}

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
  decklens install-skills [options]
  decklens --help

Commands:
  convert    Convert image-like presentation pages into an editable PPTX deck.
  install-skills
             Install the DeckLens Agent skill into user-global Agent skill folders.

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
  --json                      Print machine-readable install status
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
    appVersion: 'cli'
  };
}

function runInstallSkills(args) {
  const json = args.includes('--json');
  const { installAgentSkills } = loadAgentSkillInstaller();
  const result = installAgentSkills(skillInstallOptions());
  if (json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const installed = result.installed || [];
    const failed = result.failed || [];
    if (installed.length > 0) {
      console.log(`DeckLens Agent Skill installed to ${installed.length} location${installed.length === 1 ? '' : 's'}:`);
      for (const target of installed) {
        console.log(`- ${target.name}: ${target.path}`);
      }
    } else {
      console.log('No detected Agent skill locations were installed.');
    }
    if (failed.length > 0) {
      console.error(`Failed to install ${failed.length} location${failed.length === 1 ? '' : 's'}:`);
      for (const target of failed) {
        console.error(`- ${target.name}: ${target.error}`);
      }
    }
  }
  return result.failed?.length ? 1 : 0;
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

  if (command === 'install-skills') {
    return runInstallSkills(args.slice(1));
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

const fs = require('node:fs');
const crypto = require('node:crypto');
const os = require('node:os');
const path = require('node:path');

const DECKLENS_SKILL_NAME = 'decklens-convert';

function skillSourceDir({ appPath, resourcesPath, isPackaged } = {}) {
  const packagedSkill = path.join(resourcesPath || '', 'skills', DECKLENS_SKILL_NAME);
  if (isPackaged && fs.existsSync(path.join(packagedSkill, 'SKILL.md'))) {
    return packagedSkill;
  }
  return path.join(appPath || process.cwd(), 'skills', DECKLENS_SKILL_NAME);
}

function agentSkillTargets({ home = os.homedir() } = {}) {
  const definitions = [
    {
      id: 'agents',
      name: 'Agent Skills',
      productDir: path.join(home, '.agents'),
      skillsRoot: path.join(home, '.agents', 'skills'),
      alwaysOffer: true,
      installByDefault: true
    },
    {
      id: 'codex',
      name: 'Codex legacy',
      productDir: path.join(home, '.codex'),
      skillsRoot: path.join(home, '.codex', 'skills'),
      legacy: true
    },
    {
      id: 'claude',
      name: 'Claude Code legacy',
      productDir: path.join(home, '.claude'),
      skillsRoot: path.join(home, '.claude', 'skills'),
      legacy: true
    },
    {
      id: 'openclaw',
      name: 'OpenClaw legacy',
      productDir: path.join(home, '.openclaw'),
      skillsRoot: path.join(home, '.openclaw', 'skills'),
      legacy: true
    },
    {
      id: 'hermes',
      name: 'Hermes legacy',
      productDir: path.join(home, '.hermes'),
      skillsRoot: path.join(home, '.hermes', 'skills'),
      legacy: true
    }
  ];

  return definitions.map((target) => {
    const installPath = path.join(target.skillsRoot, DECKLENS_SKILL_NAME);
    const detected = target.alwaysOffer || fs.existsSync(target.productDir) || fs.existsSync(target.skillsRoot);
    const installed = fs.existsSync(path.join(installPath, 'SKILL.md'));
    return {
      id: target.id,
      name: target.name,
      path: installPath,
      detected,
      installed,
      legacy: Boolean(target.legacy),
      installByDefault: Boolean(target.installByDefault)
    };
  });
}

function assertSkillSource(options) {
  const source = skillSourceDir(options);
  const skillFile = path.join(source, 'SKILL.md');
  if (!fs.existsSync(skillFile)) {
    throw new Error(`DeckLens Agent Skill source is missing: ${skillFile}`);
  }
  return source;
}

function skillManifestPath(skillDir) {
  return path.join(skillDir, '.decklens-managed.json');
}

function managedManifest(skillDir) {
  try {
    const raw = fs.readFileSync(skillManifestPath(skillDir), 'utf8');
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function walkFiles(root) {
  if (!fs.existsSync(root)) return [];
  const entries = fs.readdirSync(root, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name === '.DS_Store' || entry.name === '.decklens-managed.json') {
      continue;
    }
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
    } else if (entry.isFile()) {
      files.push(fullPath);
    }
  }
  return files;
}

function skillHash(skillDir) {
  if (!fs.existsSync(skillDir)) return null;
  const hash = crypto.createHash('sha256');
  for (const filePath of walkFiles(skillDir).sort()) {
    const relative = path.relative(skillDir, filePath).replaceAll(path.sep, '/');
    hash.update(relative);
    hash.update('\0');
    hash.update(fs.readFileSync(filePath));
    hash.update('\0');
  }
  return hash.digest('hex');
}

function skillVersion(skillDir) {
  try {
    const content = fs.readFileSync(path.join(skillDir, 'SKILL.md'), 'utf8');
    const frontmatter = content.match(/^---\n([\s\S]*?)\n---/);
    const source = frontmatter ? frontmatter[1] : content;
    const match = source.match(/^\s*version:\s*["']?([^"'\n]+)["']?\s*$/m);
    return match ? match[1].trim() : null;
  } catch {
    return null;
  }
}

function compareVersions(a, b) {
  const left = String(a || '').split('.').map((part) => Number.parseInt(part, 10) || 0);
  const right = String(b || '').split('.').map((part) => Number.parseInt(part, 10) || 0);
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    if ((left[index] || 0) > (right[index] || 0)) return 1;
    if ((left[index] || 0) < (right[index] || 0)) return -1;
  }
  return 0;
}

function targetWithInstallState(target, sourceInfo) {
  const installed = fs.existsSync(path.join(target.path, 'SKILL.md'));
  const manifest = installed ? managedManifest(target.path) : null;
  const currentHash = installed ? skillHash(target.path) : null;
  const currentVersion = installed ? (manifest?.skillVersion || skillVersion(target.path)) : null;
  const managed = Boolean(manifest);
  const modified = Boolean(manifest?.installedHash && currentHash && currentHash !== manifest.installedHash);
  const legacyManaged = managed && !manifest?.installedHash;
  const updateAvailable = Boolean(
    installed &&
    !modified &&
    (
      legacyManaged ||
      (sourceInfo.version && currentVersion && compareVersions(sourceInfo.version, currentVersion) > 0) ||
      (manifest?.sourceHash && sourceInfo.hash && manifest.sourceHash !== sourceInfo.hash)
    )
  );
  let state = 'not-installed';
  if (installed && !managed) state = 'unmanaged';
  else if (modified) state = 'modified';
  else if (updateAvailable) state = 'update-available';
  else if (installed) state = 'current';

  return {
    ...target,
    installed,
    managed,
    modified,
    updateAvailable,
    state,
    skillVersion: currentVersion,
    latestVersion: sourceInfo.version,
    currentHash,
    installedHash: manifest?.installedHash || null,
    sourceHash: sourceInfo.hash
  };
}

function sourceInfo(options = {}) {
  const source = skillSourceDir(options);
  return {
    source,
    sourceAvailable: fs.existsSync(path.join(source, 'SKILL.md')),
    version: skillVersion(source),
    hash: skillHash(source)
  };
}

function safeInstallSkillTarget(target, source, { appVersion = 'dev', force = false, sourceHash = null, sourceVersion = null } = {}) {
  const destination = path.resolve(target.path);
  const expectedParent = path.resolve(target.path, '..');
  const skillFile = path.join(destination, 'SKILL.md');
  if (fs.existsSync(skillFile)) {
    const content = fs.readFileSync(skillFile, 'utf8');
    if (!/^name:\s*decklens-convert\s*$/m.test(content)) {
      throw new Error(`${target.name} already has a different skill at ${destination}`);
    }
    const manifest = managedManifest(destination);
    const currentHash = skillHash(destination);
    if (!manifest && !force) {
      return { skipped: true, reason: 'unmanaged' };
    }
    if (manifest?.installedHash && currentHash !== manifest.installedHash && !force) {
      return { skipped: true, reason: 'modified' };
    }
  }
  fs.mkdirSync(expectedParent, { recursive: true });
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(source, destination, {
    recursive: true,
    filter: (src) => path.basename(src) !== '.DS_Store'
  });
  fs.writeFileSync(
    skillManifestPath(destination),
    JSON.stringify({
      name: DECKLENS_SKILL_NAME,
      skillVersion: sourceVersion || skillVersion(source),
      sourceHash: sourceHash || skillHash(source),
      installedHash: skillHash(destination),
      installedAt: new Date().toISOString(),
      appVersion,
      managed: true
    }, null, 2)
  );
  return { installed: true };
}

function safeRemoveManagedTarget(target, { force = false } = {}) {
  const destination = path.resolve(target.path);
  const skillFile = path.join(destination, 'SKILL.md');
  if (!fs.existsSync(skillFile)) {
    return { skipped: true, reason: 'not-installed' };
  }
  const content = fs.readFileSync(skillFile, 'utf8');
  if (!/^name:\s*decklens-convert\s*$/m.test(content)) {
    return { skipped: true, reason: 'different-skill' };
  }
  const manifest = managedManifest(destination);
  if (!manifest && !force) {
    return { skipped: true, reason: 'unmanaged' };
  }
  const currentHash = skillHash(destination);
  if (manifest?.installedHash && currentHash !== manifest.installedHash && !force) {
    return { skipped: true, reason: 'modified' };
  }
  fs.rmSync(destination, { recursive: true, force: true });
  return { removed: true };
}

function getAgentSkillStatus(options = {}) {
  const info = sourceInfo(options);
  const targets = agentSkillTargets(options).map((target) => targetWithInstallState(target, info));
  const visibleTargets = targets.filter((target) => target.installByDefault || target.installed);
  return {
    source: info.source,
    sourceAvailable: info.sourceAvailable,
    sourceVersion: info.version,
    sourceHash: info.hash,
    targets,
    visibleTargets,
    installedCount: targets.filter((target) => target.installed).length,
    detectedCount: visibleTargets.length,
    updateAvailableCount: targets.filter((target) => target.updateAvailable).length,
    modifiedCount: targets.filter((target) => target.modified).length
  };
}

function installAgentSkills(options = {}) {
  const source = assertSkillSource(options);
  const info = sourceInfo(options);
  const targets = agentSkillTargets(options);
  const installTargets = targets.filter((target) => target.installByDefault);
  const cleanupTargets = targets.filter((target) => target.legacy && target.installed);
  const installed = [];
  const removed = [];
  const skipped = [];
  const failed = [];

  for (const target of installTargets) {
    try {
      const result = safeInstallSkillTarget(target, source, { ...options, sourceHash: info.hash, sourceVersion: info.version });
      if (result.skipped) {
        skipped.push({ ...target, reason: result.reason });
      } else {
        installed.push({ ...target, installed: true });
      }
    } catch (error) {
      failed.push({ ...target, error: error.message });
    }
  }

  for (const target of cleanupTargets) {
    try {
      const result = safeRemoveManagedTarget(target, options);
      if (result.removed) {
        removed.push({ ...target, installed: false });
      } else if (result.skipped && result.reason !== 'not-installed') {
        skipped.push({ ...target, reason: `legacy-${result.reason}` });
      }
    } catch (error) {
      failed.push({ ...target, error: error.message });
    }
  }

  return {
    ...getAgentSkillStatus(options),
    installed,
    removed,
    skipped,
    failed
  };
}

function updateAgentSkills(options = {}) {
  const source = assertSkillSource(options);
  const info = sourceInfo(options);
  const status = getAgentSkillStatus(options);
  const updateTargets = status.targets.filter((target) => target.installByDefault && (target.detected || target.installed));
  const cleanupTargets = status.targets.filter((target) => target.legacy && target.installed);
  const installed = [];
  const removed = [];
  const skipped = [];
  const failed = [];

  for (const target of updateTargets) {
    try {
      const result = safeInstallSkillTarget(target, source, { ...options, sourceHash: info.hash, sourceVersion: info.version });
      if (result.skipped) {
        skipped.push({ ...target, reason: result.reason });
      } else {
        installed.push({ ...target, installed: true });
      }
    } catch (error) {
      failed.push({ ...target, error: error.message });
    }
  }

  for (const target of cleanupTargets) {
    try {
      const result = safeRemoveManagedTarget(target, options);
      if (result.removed) {
        removed.push({ ...target, installed: false });
      } else if (result.skipped && result.reason !== 'not-installed') {
        skipped.push({ ...target, reason: `legacy-${result.reason}` });
      }
    } catch (error) {
      failed.push({ ...target, error: error.message });
    }
  }

  return {
    ...getAgentSkillStatus(options),
    installed,
    removed,
    skipped,
    failed
  };
}

module.exports = {
  DECKLENS_SKILL_NAME,
  agentSkillTargets,
  getAgentSkillStatus,
  installAgentSkills,
  skillHash,
  skillSourceDir,
  skillVersion,
  updateAgentSkills
};

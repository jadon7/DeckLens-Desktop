const fs = require('node:fs');
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
      id: 'codex',
      name: 'Codex',
      productDir: path.join(home, '.codex'),
      skillsRoot: path.join(home, '.codex', 'skills')
    },
    {
      id: 'claude',
      name: 'Claude Code',
      productDir: path.join(home, '.claude'),
      skillsRoot: path.join(home, '.claude', 'skills')
    },
    {
      id: 'agents',
      name: 'Agent Skills',
      productDir: path.join(home, '.agents'),
      skillsRoot: path.join(home, '.agents', 'skills'),
      alwaysOffer: true
    },
    {
      id: 'openclaw',
      name: 'OpenClaw',
      productDir: path.join(home, '.openclaw'),
      skillsRoot: path.join(home, '.openclaw', 'skills')
    },
    {
      id: 'hermes',
      name: 'Hermes',
      productDir: path.join(home, '.hermes'),
      skillsRoot: path.join(home, '.hermes', 'skills')
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
      installed
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

function safeInstallSkillTarget(target, source, { appVersion = 'dev' } = {}) {
  const destination = path.resolve(target.path);
  const expectedParent = path.resolve(target.path, '..');
  const skillFile = path.join(destination, 'SKILL.md');
  if (fs.existsSync(skillFile)) {
    const content = fs.readFileSync(skillFile, 'utf8');
    if (!/^name:\s*decklens-convert\s*$/m.test(content)) {
      throw new Error(`${target.name} already has a different skill at ${destination}`);
    }
  }
  fs.mkdirSync(expectedParent, { recursive: true });
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(source, destination, {
    recursive: true,
    filter: (src) => path.basename(src) !== '.DS_Store'
  });
  fs.writeFileSync(
    path.join(destination, '.decklens-managed.json'),
    JSON.stringify({ name: DECKLENS_SKILL_NAME, installedAt: new Date().toISOString(), appVersion }, null, 2)
  );
}

function getAgentSkillStatus(options = {}) {
  const source = skillSourceDir(options);
  const sourceAvailable = fs.existsSync(path.join(source, 'SKILL.md'));
  const targets = agentSkillTargets(options);
  const visibleTargets = targets.filter((target) => target.detected || target.installed);
  return {
    source,
    sourceAvailable,
    targets,
    visibleTargets,
    installedCount: targets.filter((target) => target.installed).length,
    detectedCount: visibleTargets.length
  };
}

function installAgentSkills(options = {}) {
  const source = assertSkillSource(options);
  const targets = agentSkillTargets(options);
  const installTargets = targets.filter((target) => target.detected || target.installed);
  const installed = [];
  const failed = [];

  for (const target of installTargets) {
    try {
      safeInstallSkillTarget(target, source, options);
      installed.push({ ...target, installed: true });
    } catch (error) {
      failed.push({ ...target, error: error.message });
    }
  }

  return {
    ...getAgentSkillStatus(options),
    installed,
    failed
  };
}

module.exports = {
  DECKLENS_SKILL_NAME,
  agentSkillTargets,
  getAgentSkillStatus,
  installAgentSkills,
  skillSourceDir
};

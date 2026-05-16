#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const JSZip = require('jszip');

const ROOT_DIR = path.resolve(__dirname, '..');

function printHelp() {
  console.log(`DeckLens CLI

Usage:
  decklens convert <input...> [options]
  decklens inspect <deck.pptx> [options]
  decklens icons find <name> [options]
  decklens icons render <name> [options]
  decklens icons libraries [options]
  decklens install-skills [options]
  decklens skills status [options]
  decklens skills update [options]
  decklens --help

Commands:
  convert    Convert image-like presentation pages into an editable PPTX deck.
  inspect    Inspect a PPTX deck and print slide/layer structure for Agent review.
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
  --format <svg|png>          Output format for icons render
  --color <hex>               Icon color for icons render, default 111111
  --size <px>                 PNG size for icons render, default 512
  --output <file>             Output file for icons render
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

function positionalArgs(args, valueOptions = new Set()) {
  const positional = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (valueOptions.has(arg)) {
      index += 1;
      continue;
    }
    if (!arg.startsWith('--')) positional.push(arg);
  }
  return positional;
}

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
}

function decodeXml(value) {
  return String(value || '')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function parseXmlAttributes(tag) {
  const attributes = {};
  const regex = /([A-Za-z_][\w:.-]*)="([^"]*)"/g;
  let match = regex.exec(tag);
  while (match) {
    attributes[match[1]] = decodeXml(match[2]);
    match = regex.exec(tag);
  }
  return attributes;
}

function attrValue(attributes, name) {
  if (attributes[name] !== undefined) return attributes[name];
  const suffix = `:${name}`;
  const key = Object.keys(attributes).find((candidate) => candidate.endsWith(suffix));
  return key ? attributes[key] : undefined;
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

function iconCandidateNames(name) {
  const names = [name];
  if (name === 'globe') names.push('globe-2', 'globe-alt', 'globe-americas', 'world');
  if (name === 'mail') names.push('envelope');
  if (name === 'user') names.push('user-circle');
  return names;
}

function findIconMatches(name, preferredStyle) {
  const matches = [];
  const seenPaths = new Set();
  for (const library of existingIconLibraries()) {
    if (preferredStyle && library.style !== preferredStyle) continue;
    if (library.extension === 'font') continue;
    for (const candidateName of iconCandidateNames(name)) {
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
  return matches;
}

function findIcons(args) {
  const json = args.includes('--json');
  const preferredStyle = optionValue(args, '--style');
  const positional = positionalArgs(args, new Set(['--style']));
  const name = normalizeIconName(positional[0] || '');
  if (!name) {
    throw new Error('Icon name is required. Example: decklens icons find mail --json');
  }

  const matches = findIconMatches(name, preferredStyle);

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

function normalizeIconColor(value) {
  const input = String(value || '111111').trim().replace(/^#/, '');
  if (!/^[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/.test(input)) {
    throw new Error(`Invalid icon color "${value}". Use hex like 111111 or #509CF8.`);
  }
  if (input.length === 3) {
    return `#${input.split('').map((char) => char + char).join('')}`;
  }
  return `#${input}`;
}

function colorizeSvg(svg, color) {
  let output = svg.replace(/currentColor/g, color);
  output = output.replace(/stroke=(["'])(?!none\b)[^"']+\1/g, `stroke="${color}"`);
  output = output.replace(/fill=(["'])(?!none\b)[^"']+\1/g, `fill="${color}"`);
  if (!/\s(fill|stroke)=/.test(output)) {
    output = output.replace('<svg ', `<svg fill="${color}" `);
  }
  return output;
}

async function renderIcon(args) {
  const json = args.includes('--json');
  const preferredStyle = optionValue(args, '--style');
  const format = String(optionValue(args, '--format') || 'svg').toLowerCase();
  const outputPath = optionValue(args, '--output');
  const size = Number(optionValue(args, '--size') || 512);
  const color = normalizeIconColor(optionValue(args, '--color'));
  const positional = positionalArgs(args, new Set(['--style', '--format', '--output', '--size', '--color']));
  const name = normalizeIconName(positional[0] || '');

  if (!name) {
    throw new Error('Icon name is required. Example: decklens icons render mail --format png --output mail.png');
  }
  if (!outputPath) {
    throw new Error('--output is required for icons render.');
  }
  if (!['svg', 'png'].includes(format)) {
    throw new Error('--format must be svg or png.');
  }
  if (!Number.isFinite(size) || size < 16 || size > 4096) {
    throw new Error('--size must be a number from 16 to 4096.');
  }

  const matches = findIconMatches(name, preferredStyle);
  if (!matches.length) {
    throw new Error(`No bundled SVG icon found for "${name}".`);
  }

  const match = matches[0];
  const svg = colorizeSvg(fs.readFileSync(match.path, 'utf8'), color);
  ensureParentDir(outputPath);

  if (format === 'svg') {
    fs.writeFileSync(outputPath, svg, 'utf8');
  } else {
    let sharp;
    try {
      sharp = require('sharp');
    } catch (error) {
      throw new Error(`PNG icon rendering requires sharp, but it is not available: ${error.message}`);
    }
    await sharp(Buffer.from(svg))
      .resize(size, size, { fit: 'contain' })
      .png()
      .toFile(outputPath);
  }

  const result = {
    query: name,
    icon: match,
    output: path.resolve(outputPath),
    format,
    color,
    size: format === 'png' ? size : null
  };
  if (json) console.log(JSON.stringify(result, null, 2));
  else console.log(`${match.library}/${match.style}/${match.name} -> ${result.output}`);
  return 0;
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

async function runIcons(args) {
  const subcommand = args[0] || 'libraries';
  if (subcommand === 'find') {
    return findIcons(args.slice(1));
  }
  if (subcommand === 'render') {
    return renderIcon(args.slice(1));
  }
  if (subcommand === 'libraries') {
    return listIconLibraries(args.slice(1));
  }
  console.error(`Unknown icons command: ${subcommand}`);
  printHelp();
  return 1;
}

function parseRelationships(xml) {
  const relationships = {};
  const regex = /<Relationship\b([^>]+?)\/?>/g;
  let match = regex.exec(xml || '');
  while (match) {
    const attributes = parseXmlAttributes(match[1]);
    if (attributes.Id) {
      relationships[attributes.Id] = {
        id: attributes.Id,
        type: attributes.Type || '',
        target: attributes.Target || '',
        targetMode: attributes.TargetMode || ''
      };
    }
    match = regex.exec(xml || '');
  }
  return relationships;
}

function parseContentTypes(xml) {
  const defaults = {};
  const overrides = {};
  const defaultRegex = /<Default\b([^>]+?)\/?>/g;
  let match = defaultRegex.exec(xml || '');
  while (match) {
    const attributes = parseXmlAttributes(match[1]);
    if (attributes.Extension && attributes.ContentType) {
      defaults[attributes.Extension.toLowerCase()] = attributes.ContentType;
    }
    match = defaultRegex.exec(xml || '');
  }
  const overrideRegex = /<Override\b([^>]+?)\/?>/g;
  match = overrideRegex.exec(xml || '');
  while (match) {
    const attributes = parseXmlAttributes(match[1]);
    if (attributes.PartName && attributes.ContentType) {
      overrides[attributes.PartName.replace(/^\/+/, '')] = attributes.ContentType;
    }
    match = overrideRegex.exec(xml || '');
  }
  return { defaults, overrides };
}

function contentTypeFor(partName, contentTypes) {
  const normalized = partName.replace(/^\/+/, '');
  if (contentTypes.overrides[normalized]) return contentTypes.overrides[normalized];
  const extension = path.posix.extname(normalized).replace('.', '').toLowerCase();
  return contentTypes.defaults[extension] || null;
}

function resolvePptTarget(sourcePath, target) {
  if (!target) return null;
  if (/^[a-z]+:/i.test(target)) return target;
  const cleaned = target.replace(/^\/+/, '');
  if (target.startsWith('/')) return cleaned;
  return path.posix.normalize(path.posix.join(path.posix.dirname(sourcePath), cleaned));
}

function parsePresentationSize(xml) {
  const match = /<p:sldSz\b([^>]+?)\/?>/.exec(xml || '');
  if (!match) return null;
  const attributes = parseXmlAttributes(match[1]);
  const widthEmu = Number(attrValue(attributes, 'cx'));
  const heightEmu = Number(attrValue(attributes, 'cy'));
  if (!Number.isFinite(widthEmu) || !Number.isFinite(heightEmu)) return null;
  return {
    widthEmu,
    heightEmu,
    widthIn: Number((widthEmu / 914400).toFixed(3)),
    heightIn: Number((heightEmu / 914400).toFixed(3))
  };
}

function parseTransform(xml) {
  const transform = { x: 0, y: 0, w: 0, h: 0 };
  const offMatch = /<a:off\b([^>]+?)\/?>/.exec(xml);
  const extMatch = /<a:ext\b([^>]+?)\/?>/.exec(xml);
  if (offMatch) {
    const attributes = parseXmlAttributes(offMatch[1]);
    transform.x = Number(attrValue(attributes, 'x') || 0);
    transform.y = Number(attrValue(attributes, 'y') || 0);
  }
  if (extMatch) {
    const attributes = parseXmlAttributes(extMatch[1]);
    transform.w = Number(attrValue(attributes, 'cx') || 0);
    transform.h = Number(attrValue(attributes, 'cy') || 0);
  }
  return {
    xEmu: transform.x,
    yEmu: transform.y,
    wEmu: transform.w,
    hEmu: transform.h,
    xIn: Number((transform.x / 914400).toFixed(3)),
    yIn: Number((transform.y / 914400).toFixed(3)),
    wIn: Number((transform.w / 914400).toFixed(3)),
    hIn: Number((transform.h / 914400).toFixed(3))
  };
}

function parseShapeBlock(block, tag, index, relationships, slidePath, contentTypes) {
  const cNvPrMatch = /<p:cNvPr\b([^>]+?)\/?>/.exec(block);
  const cNvPr = cNvPrMatch ? parseXmlAttributes(cNvPrMatch[1]) : {};
  const text = Array.from(block.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g))
    .map((match) => decodeXml(match[1]))
    .join('');
  const transform = parseTransform(block);
  const item = {
    index,
    z: index,
    type: tag === 'pic' ? 'picture' : tag === 'grpSp' ? 'group' : tag === 'cxnSp' ? 'connector' : text ? 'text' : 'shape',
    name: cNvPr.name || '',
    id: cNvPr.id || null,
    text: text || null,
    ...transform
  };

  if (tag === 'pic') {
    const blipMatch = /<a:blip\b([^>]+?)\/?>/.exec(block);
    const attributes = blipMatch ? parseXmlAttributes(blipMatch[1]) : {};
    const relationshipId = attrValue(attributes, 'embed') || attrValue(attributes, 'link') || null;
    const relationship = relationshipId ? relationships[relationshipId] : null;
    const mediaPath = relationship ? resolvePptTarget(slidePath, relationship.target) : null;
    item.relationshipId = relationshipId;
    item.target = relationship?.target || null;
    item.mediaPath = mediaPath;
    item.contentType = mediaPath ? contentTypeFor(mediaPath, contentTypes) : null;
  }

  const geometryMatch = /<a:prstGeom\b([^>]+?)>/.exec(block) || /<a:prstGeom\b([^>]+?)\/>/.exec(block);
  if (geometryMatch) {
    item.shapeType = parseXmlAttributes(geometryMatch[1]).prst || null;
  }
  return item;
}

function parseSlideItems(xml, relationships, slidePath, contentTypes) {
  const treeMatch = /<p:spTree[\s\S]*?>([\s\S]*?)<\/p:spTree>/.exec(xml || '');
  if (!treeMatch) return [];
  const childRegex = /<p:(pic|sp|cxnSp|grpSp)\b[\s\S]*?<\/p:\1>/g;
  const items = [];
  let match = childRegex.exec(treeMatch[1]);
  while (match) {
    items.push(parseShapeBlock(match[0], match[1], items.length + 1, relationships, slidePath, contentTypes));
    match = childRegex.exec(treeMatch[1]);
  }
  return items;
}

async function inspectPptx(args) {
  const json = args.includes('--json');
  const positional = positionalArgs(args);
  const inputPath = positional[0];
  if (!inputPath) {
    throw new Error('PPTX path is required. Example: decklens inspect output.pptx --json');
  }
  const resolvedInput = path.resolve(inputPath);
  if (!fileExists(resolvedInput)) {
    throw new Error(`PPTX file was not found: ${resolvedInput}`);
  }

  const zip = await JSZip.loadAsync(await fs.promises.readFile(resolvedInput));
  const readText = async (filePath) => {
    const file = zip.file(filePath);
    return file ? file.async('text') : '';
  };

  const contentTypes = parseContentTypes(await readText('[Content_Types].xml'));
  const presentationSize = parsePresentationSize(await readText('ppt/presentation.xml'));
  const media = [];
  for (const filePath of Object.keys(zip.files).sort()) {
    if (filePath.startsWith('ppt/media/') && !zip.files[filePath].dir) {
      media.push({
        path: filePath,
        bytes: zip.files[filePath]._data?.uncompressedSize || null,
        contentType: contentTypeFor(filePath, contentTypes)
      });
    }
  }

  const slidePaths = Object.keys(zip.files)
    .filter((filePath) => /^ppt\/slides\/slide\d+\.xml$/.test(filePath))
    .sort((a, b) => Number(a.match(/slide(\d+)\.xml$/)[1]) - Number(b.match(/slide(\d+)\.xml$/)[1]));

  const slides = [];
  for (const slidePath of slidePaths) {
    const slideNumber = Number(slidePath.match(/slide(\d+)\.xml$/)[1]);
    const relationshipsPath = `ppt/slides/_rels/slide${slideNumber}.xml.rels`;
    const relationships = parseRelationships(await readText(relationshipsPath));
    const items = parseSlideItems(await readText(slidePath), relationships, slidePath, contentTypes);
    slides.push({
      index: slides.length + 1,
      slideNumber,
      path: slidePath,
      size: presentationSize,
      summary: {
        items: items.length,
        pictures: items.filter((item) => item.type === 'picture').length,
        text: items.filter((item) => item.type === 'text').length,
        shapes: items.filter((item) => ['shape', 'connector', 'group'].includes(item.type)).length
      },
      items
    });
  }

  const result = {
    path: resolvedInput,
    slideCount: slides.length,
    mediaCount: media.length,
    media,
    slides
  };

  if (json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`${path.basename(resolvedInput)}: ${slides.length} slide${slides.length === 1 ? '' : 's'}, ${media.length} media file${media.length === 1 ? '' : 's'}`);
    for (const slide of slides) {
      console.log(`- slide ${slide.index}: ${slide.summary.items} items, ${slide.summary.pictures} pictures, ${slide.summary.text} text, ${slide.summary.shapes} shapes`);
    }
  }
  return 0;
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
  const removed = result.removed || [];
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
  if (removed.length > 0) {
    console.log(`Removed ${removed.length} legacy location${removed.length === 1 ? '' : 's'}:`);
    for (const target of removed) {
      console.log(`- ${target.name}: ${target.path}`);
    }
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

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  if (!command || command === '--help' || command === '-h') {
    printHelp();
    return 0;
  }

  if (command === 'convert') {
    return runConvert(args.slice(1));
  }

  if (command === 'inspect') {
    return inspectPptx(args.slice(1));
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

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`DeckLens CLI failed: ${error.message}`);
  process.exitCode = 1;
});

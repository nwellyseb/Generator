#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f package.json || ! -d src/remotion ]]; then
  echo "Run this script from inside your hybrid-tutorial-starter folder."
  echo "Example: cd ~/Downloads/hybrid-tutorial-starter"
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR=".backup-before-generator-v2-$STAMP"
mkdir -p "$BACKUP_DIR"

for item in package.json README.md src/storyboard.ts scripts/capture-browser.mjs; do
  if [[ -f "$item" ]]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$item")"
    cp "$item" "$BACKUP_DIR/$item"
  fi
done

mkdir -p project scripts public/generated out

node <<'NODE'
const fs = require('node:fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
pkg.name = 'nwellyseb-hybrid-tutorial-generator';
pkg.version = '0.2.0';
pkg.description = 'Terminal-driven Full HD animated explainer and automated browser tutorial generator.';
pkg.scripts = {
  ...(pkg.scripts || {}),
  create: 'node scripts/create-project.mjs',
  'capture:browser': 'node scripts/capture-browser.mjs',
  studio: 'remotion studio src/remotion/index.ts',
  render: 'node scripts/render-video.mjs',
  'build:current': 'node scripts/build-video.mjs',
  make: 'npm run create && npm run build:current',
  check: 'node scripts/check-project.mjs'
};
fs.writeFileSync('package.json', `${JSON.stringify(pkg, null, 2)}\n`);
NODE
cat > project/storyboard.json <<'NWELLYSEB_FILE_0_END'
{
  "title": "How to organize browser tabs",
  "channelName": "nwellyseb",
  "scenes": [
    {
      "id": "intro",
      "type": "animated",
      "durationInFrames": 150,
      "eyebrow": "NWELLYSEB TUTORIAL",
      "title": "How to organize browser tabs",
      "body": "A clear beginners guide with animated explanations and a real browser demonstration.",
      "narration": "Welcome to nwellyseb. In this tutorial, you will learn how to organize browser tabs in a clear, practical way."
    },
    {
      "id": "explanation",
      "type": "animated",
      "durationInFrames": 240,
      "eyebrow": "WHAT YOU WILL LEARN",
      "title": "The essentials of How to organize browser tabs",
      "bullets": [
        "Understand tab groups",
        "Create a group",
        "Name and save it"
      ],
      "narration": "We will focus on Understand tab groups, Create a group, Name and save it."
    },
    {
      "id": "browser-demo",
      "type": "browser",
      "durationInFrames": 510,
      "videoFile": "generated/browser-demo.webm",
      "label": "Real automated browser footage",
      "narration": "Now follow the real browser demonstration. Select Create a new tutorial. Enter the required information in Tutorial topic. Choose the correct option in Video style. Select Generate Full HD video."
    },
    {
      "id": "summary",
      "type": "animated",
      "durationInFrames": 180,
      "eyebrow": "QUICK RECAP",
      "title": "You are ready to continue",
      "bullets": [
        "Understand tab groups",
        "Create a group",
        "Name and save it",
        "You can now keep browser tabs organized"
      ],
      "narration": "You can now keep browser tabs organized Review the result, practice the steps, and subscribe to nwellyseb for more tutorials."
    }
  ]
}
NWELLYSEB_FILE_0_END

cat > project/browser-plan.json <<'NWELLYSEB_FILE_1_END'
{
  "enabled": true,
  "url": "demo://local",
  "outputFile": "public/generated/browser-demo.webm",
  "actions": [
    {
      "type": "click",
      "by": "role",
      "role": "button",
      "name": "Create a new tutorial"
    },
    {
      "type": "fill",
      "by": "label",
      "name": "Tutorial topic",
      "value": "How to organize browser tabs"
    },
    {
      "type": "select",
      "by": "label",
      "name": "Video style",
      "value": "tutorial"
    },
    {
      "type": "click",
      "by": "role",
      "role": "button",
      "name": "Generate Full HD video"
    },
    {
      "type": "wait",
      "ms": 1800
    }
  ]
}
NWELLYSEB_FILE_1_END

cat > src/storyboard.ts <<'NWELLYSEB_FILE_2_END'
import generatedStoryboard from '../project/storyboard.json';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export type AnimatedScene = {
  id: string;
  type: 'animated';
  durationInFrames: number;
  eyebrow?: string;
  title: string;
  body?: string;
  bullets?: string[];
  narration: string;
};

export type BrowserScene = {
  id: string;
  type: 'browser';
  durationInFrames: number;
  videoFile: string;
  label: string;
  narration: string;
};

export type TutorialScene = AnimatedScene | BrowserScene;

export type TutorialStoryboard = {
  title: string;
  channelName: string;
  scenes: TutorialScene[];
};

function validateStoryboard(value: unknown): asserts value is TutorialStoryboard {
  if (!value || typeof value !== 'object') {
    throw new Error('project/storyboard.json must contain an object.');
  }

  const candidate = value as Partial<TutorialStoryboard>;
  if (!candidate.title || !candidate.channelName || !Array.isArray(candidate.scenes)) {
    throw new Error('Storyboard requires title, channelName, and scenes.');
  }

  if (candidate.scenes.length === 0) {
    throw new Error('Storyboard must contain at least one scene.');
  }

  for (const scene of candidate.scenes) {
    if (!scene.id || !scene.type || !Number.isFinite(scene.durationInFrames)) {
      throw new Error('Every scene requires id, type, and durationInFrames.');
    }
  }
}

validateStoryboard(generatedStoryboard);

export const sampleStoryboard: TutorialStoryboard = generatedStoryboard;

export const totalDurationInFrames = sampleStoryboard.scenes.reduce(
  (sum, scene) => sum + scene.durationInFrames,
  0,
);
NWELLYSEB_FILE_2_END

cat > scripts/create-project.mjs <<'NWELLYSEB_FILE_3_END'
import {mkdir, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createInterface} from 'node:readline/promises';
import {stdin as input, stdout as output} from 'node:process';

const FPS = 30;
const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const projectDir = resolve(rootDir, 'project');
const storyboardFile = resolve(projectDir, 'storyboard.json');
const browserPlanFile = resolve(projectDir, 'browser-plan.json');

let rl = null;
let queuedAnswers = [];

if (input.isTTY) {
  rl = createInterface({input, output});
} else {
  let pipedInput = '';
  for await (const chunk of input) {
    pipedInput += chunk;
  }
  queuedAnswers = pipedInput.split(/\r?\n/);
}

function clean(value, fallback) {
  const trimmed = String(value ?? '').trim();
  return trimmed || fallback;
}

async function ask(question, fallback = '') {
  const suffix = fallback ? ` [${fallback}]` : '';
  if (rl) {
    const answer = await rl.question(`${question}${suffix}: `);
    return clean(answer, fallback);
  }

  const answer = queuedAnswers.shift() ?? '';
  console.log(`${question}${suffix}: ${answer}`);
  return clean(answer, fallback);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function toFrames(seconds) {
  return Math.max(FPS, Math.round(seconds * FPS));
}

function sentence(value) {
  const text = String(value).trim();
  if (!text) return '';
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

function splitPoints(value) {
  return String(value)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function parseBrowserActions(raw) {
  if (!raw.trim()) {
    return [
      {type: 'wait', ms: 1200},
      {type: 'scroll', y: 650},
      {type: 'wait', ms: 1200},
      {type: 'scroll', y: -250},
      {type: 'wait', ms: 900},
    ];
  }

  return raw
    .split(';')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry, index) => {
      const parts = entry.split(':').map((part) => part.trim());
      const type = parts[0]?.toLowerCase();

      if (type === 'wait') {
        return {type: 'wait', ms: Number(parts[1] || 1000)};
      }
      if (type === 'scroll') {
        return {type: 'scroll', y: Number(parts[1] || 600)};
      }
      if (type === 'press') {
        return {type: 'press', key: parts.slice(1).join(':') || 'Escape'};
      }
      if (type === 'click') {
        const by = parts[1] || 'text';
        if (by === 'role') {
          return {
            type: 'click',
            by,
            role: parts[2] || 'button',
            name: parts.slice(3).join(':'),
          };
        }
        return {type: 'click', by, name: parts.slice(2).join(':')};
      }
      if (type === 'fill' || type === 'select') {
        const by = parts[1] || 'label';
        const name = parts[2] || '';
        const value = parts.slice(3).join(':');
        return {type, by, name, value};
      }

      throw new Error(`Browser action ${index + 1} is invalid: ${entry}`);
    });
}

function describeActions(actions) {
  return actions
    .filter((action) => ['click', 'fill', 'select'].includes(action.type))
    .map((action) => {
      if (action.type === 'click') return `Select ${action.name || action.role || 'the highlighted control'}`;
      if (action.type === 'fill') return `Enter the required information in ${action.name || 'the field'}`;
      return `Choose the correct option in ${action.name || 'the menu'}`;
    })
    .slice(0, 5);
}

function createStoryboard({
  topic,
  audience,
  minutes,
  type,
  points,
  takeaway,
  actions,
}) {
  const totalSeconds = clamp(Math.round(minutes * 60), 30, 600);
  const isHybrid = type === 'hybrid';
  const browserSeconds = isHybrid
    ? clamp(Math.round(actions.length * 2.6 + 5), 12, Math.round(totalSeconds * 0.58))
    : 0;
  const animatedSeconds = totalSeconds - browserSeconds;
  const introSeconds = clamp(Math.round(animatedSeconds * 0.22), 5, 16);
  const summarySeconds = clamp(Math.round(animatedSeconds * 0.24), 6, 18);
  const teachingSeconds = Math.max(8, animatedSeconds - introSeconds - summarySeconds);
  const actionBullets = describeActions(actions);
  const teachingBullets = points.length ? points : [
    `Understand the purpose of ${topic}`,
    'Follow the process one step at a time',
    'Review the result before publishing',
  ];

  const scenes = [
    {
      id: 'intro',
      type: 'animated',
      durationInFrames: toFrames(introSeconds),
      eyebrow: 'NWELLYSEB TUTORIAL',
      title: topic,
      body: `A clear ${audience.toLowerCase()} guide with animated explanations${isHybrid ? ' and a real browser demonstration' : ''}.`,
      narration: sentence(`Welcome to nwellyseb. In this tutorial, you will learn ${topic.toLowerCase()} in a clear, practical way`),
    },
    {
      id: 'explanation',
      type: 'animated',
      durationInFrames: toFrames(teachingSeconds),
      eyebrow: 'WHAT YOU WILL LEARN',
      title: `The essentials of ${topic}`,
      bullets: teachingBullets,
      narration: sentence(`We will focus on ${teachingBullets.join(', ')}`),
    },
  ];

  if (isHybrid) {
    scenes.push({
      id: 'browser-demo',
      type: 'browser',
      durationInFrames: toFrames(browserSeconds),
      videoFile: 'generated/browser-demo.webm',
      label: 'Real automated browser footage',
      narration: sentence(
        actionBullets.length
          ? `Now follow the real browser demonstration. ${actionBullets.join('. ')}`
          : `Now watch the real browser demonstration and follow each highlighted action`,
      ),
    });
  }

  scenes.push({
    id: 'summary',
    type: 'animated',
    durationInFrames: toFrames(summarySeconds),
    eyebrow: 'QUICK RECAP',
    title: 'You are ready to continue',
    bullets: [
      ...teachingBullets.slice(0, 3),
      sentence(takeaway).replace(/[.!?]$/, ''),
    ].filter(Boolean),
    narration: sentence(`${takeaway} Review the result, practice the steps, and subscribe to nwellyseb for more tutorials`),
  });

  return {
    title: topic,
    channelName: 'nwellyseb',
    scenes,
  };
}

try {
  console.log('\nNWELLYSEB FULL HD TUTORIAL GENERATOR');
  console.log('This creates captions and visuals. AI voice-over comes in the next milestone.\n');

  const topic = await ask('Tutorial topic', 'How to create a tutorial video');
  const audience = await ask('Audience', 'Beginners');
  const minutesRaw = await ask('Approximate video length in minutes', '1');
  const minutes = clamp(Number(minutesRaw) || 1, 0.5, 10);
  const typeAnswer = (await ask('Type: animated or hybrid', 'hybrid')).toLowerCase();
  const type = typeAnswer.startsWith('a') ? 'animated' : 'hybrid';
  const points = splitPoints(
    await ask(
      'Key teaching points, separated by commas',
      'Explain the goal, Show the main steps, Review the finished result',
    ),
  );
  const takeaway = await ask('Final takeaway', `You now know how to ${topic.toLowerCase()}`);

  let browserPlan = {
    enabled: false,
    url: 'demo://local',
    outputFile: 'public/generated/browser-demo.webm',
    actions: [],
  };

  if (type === 'hybrid') {
    const url = await ask('Website URL, or type demo for the built-in test site', 'demo');
    const isDemo = url.toLowerCase() === 'demo';

    let actions;
    if (isDemo) {
      actions = [
        {type: 'click', by: 'role', role: 'button', name: 'Create a new tutorial'},
        {type: 'fill', by: 'label', name: 'Tutorial topic', value: topic},
        {type: 'select', by: 'label', name: 'Video style', value: 'tutorial'},
        {type: 'click', by: 'role', role: 'button', name: 'Generate Full HD video'},
        {type: 'wait', ms: 1800},
      ];
    } else {
      console.log('\nOptional browser actions use this format, separated by semicolons:');
      console.log('click:role:button:Create project; fill:label:Project name:My tutorial; scroll:700; wait:1000');
      console.log('Other locators: text, label, placeholder, css. Leave blank for a simple page-and-scroll recording.\n');
      actions = parseBrowserActions(await ask('Browser actions', ''));
    }

    browserPlan = {
      enabled: true,
      url: isDemo ? 'demo://local' : url,
      outputFile: 'public/generated/browser-demo.webm',
      actions,
    };
  }

  const storyboard = createStoryboard({
    topic,
    audience,
    minutes,
    type,
    points,
    takeaway,
    actions: browserPlan.actions,
  });

  await mkdir(projectDir, {recursive: true});
  await writeFile(storyboardFile, `${JSON.stringify(storyboard, null, 2)}\n`, 'utf8');
  await writeFile(browserPlanFile, `${JSON.stringify(browserPlan, null, 2)}\n`, 'utf8');

  console.log('\nProject created successfully.');
  console.log(`Storyboard: ${storyboardFile}`);
  console.log(`Browser plan: ${browserPlanFile}`);
  console.log('\nRun npm run build:current to create the Full HD MP4.\n');
} finally {
  rl?.close();
}
NWELLYSEB_FILE_3_END

cat > scripts/capture-browser.mjs <<'NWELLYSEB_FILE_4_END'
import {copyFile, mkdir, readFile, rm} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {chromium} from 'playwright';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const planFile = resolve(rootDir, 'project/browser-plan.json');
const demoFile = resolve(rootDir, 'demo-site/index.html');
const rawDir = resolve(rootDir, '.browser-recordings');

const plan = JSON.parse(await readFile(planFile, 'utf8'));
if (!plan.enabled) {
  console.log('No browser scene is enabled. Skipping browser capture.');
  process.exit(0);
}

const outputFile = resolve(rootDir, plan.outputFile || 'public/generated/browser-demo.webm');
const targetUrl = plan.url === 'demo://local' ? pathToFileURL(demoFile).href : plan.url;

if (!/^https?:\/\//.test(targetUrl) && !targetUrl.startsWith('file:')) {
  throw new Error('Browser URL must begin with http://, https://, or use demo://local.');
}

await rm(rawDir, {recursive: true, force: true});
await mkdir(rawDir, {recursive: true});
await mkdir(dirname(outputFile), {recursive: true});

const browser = await chromium.launch({headless: true});
const context = await browser.newContext({
  viewport: {width: 1920, height: 1080},
  recordVideo: {
    dir: rawDir,
    size: {width: 1920, height: 1080},
  },
});

const page = await context.newPage();
let recordedVideo;

function locatorFor(action) {
  const by = action.by || 'text';
  if (by === 'role') {
    return page.getByRole(action.role || 'button', {name: action.name});
  }
  if (by === 'label') return page.getByLabel(action.name);
  if (by === 'placeholder') return page.getByPlaceholder(action.name);
  if (by === 'css') return page.locator(action.name);
  return page.getByText(action.name, {exact: false});
}

async function installTutorialOverlay() {
  try {
    await page.addStyleTag({
      content: `
        #tutorial-cursor {
          position: fixed;
          z-index: 2147483647;
          width: 28px;
          height: 28px;
          border-radius: 999px;
          background: rgba(255,255,255,.96);
          border: 5px solid #0ea5e9;
          box-shadow: 0 5px 20px rgba(0,0,0,.45);
          pointer-events: none;
          left: 100px;
          top: 100px;
          transition: left .55s cubic-bezier(.2,.8,.2,1), top .55s cubic-bezier(.2,.8,.2,1);
        }
        .tutorial-highlight {
          outline: 5px solid #fbbf24 !important;
          outline-offset: 6px !important;
          box-shadow: 0 0 0 13px rgba(251,191,36,.18) !important;
        }
      `,
    });
    await page.evaluate(() => {
      document.querySelector('#tutorial-cursor')?.remove();
      const cursor = document.createElement('div');
      cursor.id = 'tutorial-cursor';
      document.body.append(cursor);
    });
  } catch {
    console.warn('The page blocked the visual cursor overlay. Recording will continue.');
  }
}

async function pointAt(locator) {
  const target = locator.first();
  await target.waitFor({state: 'visible', timeout: 12000});
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) return;

  try {
    await page.evaluate(() => {
      document.querySelectorAll('.tutorial-highlight').forEach((element) => {
        element.classList.remove('tutorial-highlight');
      });
    });
    await target.evaluate((element) => element.classList.add('tutorial-highlight'));
    await page.evaluate(({left, top}) => {
      const cursor = document.querySelector('#tutorial-cursor');
      if (cursor instanceof HTMLElement) {
        cursor.style.left = `${left}px`;
        cursor.style.top = `${top}px`;
      }
    }, {
      left: box.x + box.width / 2 - 14,
      top: box.y + box.height / 2 - 14,
    });
  } catch {
    // Some pages replace elements while they animate. The action can still continue.
  }

  await page.waitForTimeout(750);
}

async function runAction(action, index) {
  console.log(`Browser action ${index + 1}: ${action.type}`);

  if (action.type === 'wait') {
    await page.waitForTimeout(Number(action.ms) || 1000);
    return;
  }
  if (action.type === 'scroll') {
    await page.mouse.wheel(0, Number(action.y) || 600);
    await page.waitForTimeout(900);
    return;
  }
  if (action.type === 'press') {
    await page.keyboard.press(action.key || 'Escape');
    await page.waitForTimeout(650);
    return;
  }

  const locator = locatorFor(action);
  await pointAt(locator);

  if (action.type === 'click') {
    await locator.first().click({timeout: 12000});
  } else if (action.type === 'fill') {
    await locator.first().fill(String(action.value ?? ''), {timeout: 12000});
  } else if (action.type === 'select') {
    await locator.first().selectOption(String(action.value ?? ''), {timeout: 12000});
  } else {
    throw new Error(`Unsupported browser action type: ${action.type}`);
  }

  await page.waitForTimeout(750);
}

try {
  await page.goto(targetUrl, {waitUntil: 'domcontentloaded', timeout: 45000});
  await page.waitForTimeout(1000);
  await installTutorialOverlay();

  for (const [index, action] of (plan.actions || []).entries()) {
    await runAction(action, index);
  }

  await page.waitForTimeout(1200);
  recordedVideo = page.video();
} catch (error) {
  console.error('\nBrowser capture failed.');
  console.error(error instanceof Error ? error.message : error);
  throw error;
} finally {
  await context.close();
  await browser.close();
}

if (!recordedVideo) {
  throw new Error('Playwright did not create a browser video.');
}

const rawFile = await recordedVideo.path();
await copyFile(rawFile, outputFile);
console.log(`Full HD browser footage written to ${outputFile}`);
NWELLYSEB_FILE_4_END

cat > scripts/render-video.mjs <<'NWELLYSEB_FILE_5_END'
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const storyboard = JSON.parse(
  await readFile(resolve(rootDir, 'project/storyboard.json'), 'utf8'),
);

function slugify(value) {
  return String(value)
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 70) || 'tutorial-video';
}

const outputDir = resolve(rootDir, 'out');
const outputFile = resolve(outputDir, `${slugify(storyboard.title)}.mp4`);
await mkdir(outputDir, {recursive: true});

const args = [
  'remotion',
  'render',
  'src/remotion/index.ts',
  'HybridTutorial',
  outputFile,
  '--codec=h264',
  '--crf=18',
  '--concurrency=1',
];

const child = spawn('npx', args, {
  cwd: rootDir,
  stdio: 'inherit',
  shell: false,
});

const exitCode = await new Promise((resolveExit, reject) => {
  child.on('error', reject);
  child.on('exit', (code) => resolveExit(code ?? 1));
});

if (exitCode !== 0) {
  process.exit(exitCode);
}

await writeFile(resolve(rootDir, 'project/last-output.txt'), `${outputFile}\n`, 'utf8');
console.log(`\nFinished Full HD video: ${outputFile}`);
console.log(`Open it with: open "${outputFile}"\n`);
NWELLYSEB_FILE_5_END

cat > scripts/build-video.mjs <<'NWELLYSEB_FILE_6_END'
import {readFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const plan = JSON.parse(
  await readFile(resolve(rootDir, 'project/browser-plan.json'), 'utf8'),
);

async function runNpm(script) {
  const child = spawn('npm', ['run', script], {
    cwd: rootDir,
    stdio: 'inherit',
    shell: false,
  });

  const exitCode = await new Promise((resolveExit, reject) => {
    child.on('error', reject);
    child.on('exit', (code) => resolveExit(code ?? 1));
  });

  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

if (plan.enabled) {
  await runNpm('capture:browser');
}
await runNpm('render');
NWELLYSEB_FILE_6_END

cat > README.md <<'NWELLYSEB_FILE_7_END'
# nwellyseb Full HD Tutorial Generator

This version is driven from Terminal. It creates:

- animated explanation scenes;
- optional real Playwright browser footage;
- captions rendered from each scene's narration;
- nwellyseb branding;
- Full HD 1920 × 1080 H.264 MP4 output;
- one-at-a-time rendering for an 8 GB M1 Mac.

## Install once

```bash
npm install
npx playwright install chromium
```

## Create and render a new video

```bash
npm run make
```

The command asks for the topic, audience, length, teaching points, tutorial type, and browser information. It then captures the browser when needed and renders the MP4.

## Rebuild the current project

```bash
npm run build:current
```

## Preview in Remotion Studio

```bash
npm run studio
```

## Browser action format

For a non-demo website, browser actions are optional. Separate actions with semicolons.

```text
click:role:button:Create project; fill:label:Project name:My tutorial; scroll:700; wait:1000
```

Supported actions:

```text
click:role:button:Visible button name
click:text:Visible text
click:label:Field label
click:css:#element-id
fill:label:Email:demo@example.com
select:label:Video style:tutorial
scroll:700
wait:1200
press:Escape
```

Use public pages, demo applications, or dedicated tutorial accounts. Do not store passwords in the action plan. CAPTCHA and two-factor authentication are not bypassed.

## Files generated

```text
project/storyboard.json
project/browser-plan.json
project/last-output.txt
public/generated/browser-demo.webm
out/<tutorial-title>.mp4
```

## Current limitation

This milestone creates visual scenes, browser footage, and caption-style narration text. It does not yet synthesize spoken voice-over. That is the next layer, once dynamic project generation is stable.
NWELLYSEB_FILE_7_END

node --check scripts/create-project.mjs
node --check scripts/capture-browser.mjs
node --check scripts/render-video.mjs
node --check scripts/build-video.mjs

printf '\nUpgrade complete. Backup saved in: %s\n' "$BACKUP_DIR"
printf 'Create and render a video with:\n\n  npm run make\n\n'
printf 'Rebuild the current project with:\n\n  npm run build:current\n\n'

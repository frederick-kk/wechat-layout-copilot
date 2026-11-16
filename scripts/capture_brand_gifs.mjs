import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { createHash } from 'node:crypto';

const DEFAULT_REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const INTERVAL_MS = 125;
const sleep = (milliseconds) => new Promise(resolve => setTimeout(resolve, milliseconds));
const tap = (selector, seconds = 1) => ({ type: 'click', selector, seconds });
const hold = (selector, seconds, release = 0.7) => ({ type: 'hold', selector, seconds, release });
const wheel = (selector, deltaX, deltaY, seconds = 0.85) => ({ type: 'wheel', selector, deltaX, deltaY, seconds });

const PLANS = {
  'wechat-svg-flip-card': [tap('[data-action="forward"]', 1.25), tap('[data-action="reverse"]', 1.25)],
  'wechat-svg-envelope': [tap('[data-action="forward"]', 1.45), tap('[data-action="reverse"]', 1.45)],
  'wechat-svg-blinds': [tap('[data-action="forward"]', 1.35), tap('[data-action="reverse"]', 1.35)],
  'wechat-svg-spotlight': [tap('[data-action="left"]', 0.7), tap('[data-action="center"]', 0.7), tap('[data-action="right"]', 0.7), tap('[data-action="full"]', 0.8), tap('[data-action="reset"]', 0.55)],
  'wechat-svg-parallax': [tap('[data-action="forward"]', 1.1), tap('[data-action="back"]', 1.1)],
  'wechat-svg-accordion-panels': [tap('[data-action="pick-0-1"]', 0.85), tap('[data-action="pick-1-2"]', 0.85), tap('[data-action="pick-2-0"]', 0.85)],
  'wechat-svg-pull-tab': [tap('[data-action="open"]', 1.1), tap('[data-action="close"]', 1.1)],
  'wechat-svg-vinyl': [tap('[data-action="play"]', 3), tap('[data-action="stop"]', 0.7)],
  'wechat-svg-puzzle-assemble': [tap('[data-action="play"]', 2.6)],
  'wechat-svg-timeline': [tap('[data-action="play"]', 3)],
  'wechat-svg-confetti': [tap('[data-action="play"]', 2.4)],
  'wechat-svg-hotspots': [tap('[data-hotspot="0"]', 0.75), tap('[data-hotspot-back="0"]', 0.35), tap('[data-hotspot="1"]', 0.75), tap('[data-hotspot-back="1"]', 0.35), tap('[data-hotspot="2"]', 0.75), tap('[data-hotspot-back="2"]', 0.35)],
  'wechat-svg-switch': [tap('[data-switch-trigger="next"]', 0.85), tap('[data-switch-trigger="next"]', 0.85), tap('[data-switch-trigger="next"]', 0.85)],
  'wechat-svg-layer-peel': [tap('[data-peel-trigger="next"]', 1), tap('[data-peel-trigger="next"]', 1.2)],
  'wechat-svg-open-window': [tap('[data-window-action="open"]', 1.1), tap('[data-window-action="close"]', 1.1)],
  'wechat-svg-press-reveal': [hold('[data-press-trigger="hold"]', 2.5)],
  'wechat-svg-hold-cards': [hold('[data-hold-trigger="hold"]', 2.8)],
  'wechat-svg-wipe-compare': [tap('[data-wipe-trigger="after"]', 1.3), tap('[data-wipe-trigger="before"]', 1.3)],
  'wechat-svg-quiz': [tap('[data-quiz-choice="0"]', 0.85), tap('[data-quiz-retry="0"]', 0.4), tap('[data-quiz-choice="1"]', 0.9), tap('[data-quiz-retry="1"]', 0.4)],
  'wechat-svg-story-branches': [tap('[data-story-choice="0"]', 1), tap('[data-story-choice="0"]', 1), tap('[data-story-restart]', 1)],
  'wechat-svg-motion-path': [tap('[data-action="play"]', 2.8)],
  'wechat-svg-typewriter': [tap('[data-action="play"]', 3)],
  'wechat-svg-zoom-detail': [tap('[data-action="zoom"]', 1.2), tap('[data-action="reset"]', 1.2)],
  'wechat-svg-data-chart': [tap('[data-action="play"]', 2.5)],
  'wechat-svg-click-reveal': [tap('[data-reveal-trigger="tap"]', 2.5)],
  'wechat-svg-drawline': [{ type: 'auto', seconds: 3.2 }],
  'wechat-xiumi-gallery': [tap('[data-gallery-trigger="tap"]', 0.65), tap('[data-gallery-trigger="tap"]', 0.65), wheel('#gallery-scroll', 430, 0), wheel('#gallery-scroll', 430, 0), wheel('#gallery-scroll', -860, 0)],
  'wechat-layout-blocks': [wheel('#reading-scroll', 0, 480, 0.9), wheel('#reading-scroll', 0, 480, 0.9), wheel('#reading-scroll', 0, 480, 0.9), wheel('#reading-scroll', 0, -1440, 0.9)],
  'wechat-avatar-profile': [tap('[data-workflow-next="0"]', 0.9), tap('[data-workflow-next="1"]', 0.9), tap('[data-workflow-next="2"]', 0.9)],
  'wechat-xiumi-svg-layout': [tap('[data-workflow-next="0"]', 0.9), tap('[data-workflow-next="1"]', 0.9), tap('[data-workflow-next="2"]', 0.9)],
  'wechat-svg-tabs': [tap('[data-action="select-1"]', 1), tap('[data-action="select-2"]', 1), tap('[data-action="select-0"]', 0.8)],
  'wechat-svg-stepper': [tap('[data-action="next"]', 0.9), tap('[data-action="next"]', 0.9), tap('[data-action="finish"]', 1), tap('[data-action="restart"]', 0.8)],
  'wechat-svg-score-quiz': [tap('[data-action="answer-0"]', 0.9), tap('[data-action="answer-1"]', 0.9), tap('[data-action="answer-0"]', 1.1), tap('[data-action="restart"]', 0.8)],
  'wechat-svg-multi-select': [tap('[data-action="toggle-0"]', 0.65), tap('[data-action="toggle-1"]', 0.65), tap('[data-action="submit"]', 1.1), tap('[data-action="retry"]', 0.8)],
  'wechat-svg-checklist': [tap('[data-action="toggle-0"]', 0.8), tap('[data-action="toggle-1"]', 0.8), tap('[data-action="toggle-2"]', 1), tap('[data-action="toggle-1"]', 0.7)],
  'wechat-svg-match-pairs': [tap('[data-action="left-0"]', 0.45), tap('[data-action="right-1"]', 0.75), tap('[data-action="left-1"]', 0.45), tap('[data-action="right-2"]', 0.75), tap('[data-action="left-2"]', 0.45), tap('[data-action="right-0"]', 0.9), tap('[data-action="restart"]', 0.7)],
  'wechat-svg-progress-ring': [tap('[data-action="play"]', 2.2), tap('[data-action="reset"]', 0.7)],
  'wechat-svg-waterfall': [tap('[data-action="play"]', 2.5), tap('[data-action="reset"]', 0.7)],
  'wechat-svg-funnel': [tap('[data-action="play"]', 2.5), tap('[data-action="reset"]', 0.7)],
  'wechat-svg-radar': [tap('[data-action="play"]', 2.5), tap('[data-action="reset"]', 0.7)],
  'wechat-svg-swimlane': [tap('[data-action="step"][data-step="1"]', 1.3), tap('[data-action="reset"]', 0.8)],
  'wechat-svg-danmaku': [tap('[data-action="play"]', 3.2), tap('[data-action="stop"]', 0.7), tap('[data-action="play"]', 1.6)],
  'wechat-svg-book': [tap('[data-action="next"][data-page="0"]', 1), tap('[data-action="next"][data-page="1"]', 1), tap('[data-action="prev"][data-page="2"]', 1), tap('[data-action="home"][data-page="1"]', 0.8)],
  'wechat-svg-word-order': [tap('[data-action="pick-1"]', 0.7), tap('[data-action="pick-2"]', 0.7), tap('[data-action="pick-0"]', 1.2), tap('[data-action="restart"]', 0.8)],
  'wechat-layout-wide-table': [wheel('[data-action="scroll-table"]', 480, 0, 1), wheel('[data-action="scroll-table"]', -480, 0, 0.8)],
  'wechat-layout-dialogue': [{ type: 'auto', seconds: 2.3 }],
  'wechat-layout-annotations': [{ type: 'auto', seconds: 2.3 }],
  'wechat-layout-magazine': [{ type: 'auto', seconds: 2.3 }],
  'wechat-xiumi-faq': [tap('details[data-action="faq-item"]:nth-of-type(1) > summary', 0.7), tap('details[data-action="faq-item"]:nth-of-type(2) > summary', 0.7), tap('details[data-action="faq-item"]:nth-of-type(3) > summary', 0.9), tap('details[data-action="faq-item"]:nth-of-type(1) > summary', 0.5), tap('details[data-action="faq-item"]:nth-of-type(2) > summary', 0.5), tap('details[data-action="faq-item"]:nth-of-type(3) > summary', 0.5)],
  'wechat-xiumi-video-card': [tap('video[data-action="video-player"]', 3), tap('video[data-action="video-player"]', 0.7)],
};

async function existingCapture(filename) {
  try {
    return JSON.parse(await fs.readFile(filename, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

async function stageBounds(page) {
  return page.evaluate(() => {
    const stage = document.querySelector('#demo-stage');
    if (!stage) throw new Error('Missing #demo-stage');
    const box = stage.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height,
      viewportWidth: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth + 0.5,
      scrollX, scrollY };
  });
}

async function actionablePoint(page, selector) {
  return page.evaluate(selector => {
    for (const element of document.querySelectorAll(selector)) {
      const style = getComputedStyle(element);
      if (style.pointerEvents === 'none') continue;
      let visible = true;
      for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
        const inherited = getComputedStyle(ancestor);
        if (inherited.display === 'none' || inherited.visibility === 'hidden') {
          visible = false;
          break;
        }
      }
      if (!visible) continue;
      const box = element.getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0) continue;
      const x = box.x + box.width / 2, y = box.y + box.height / 2;
      if (x < 0 || x >= innerWidth || y < 0 || y >= innerHeight) continue;
      const hit = document.elementFromPoint(x, y);
      if (element === hit || element.contains(hit)) return { x, y };
    }
    return null;
  }, selector);
}

async function recordOne(page, entry, repo, framesRoot, overwrite) {
  const exampleDirectory = path.join(repo, 'skills', entry.slug, 'examples');
  const dependencies = [...new Set(['brand-preview.html', ...entry.assets.map(file => 'brand-assets/' + file), ...(entry.dependencies || [])])];
  const sourceHashes = {};
  for (const file of dependencies) sourceHashes[file] = createHash('sha256').update(await fs.readFile(path.join(exampleDirectory, file))).digest('hex');
  const componentDirectory = path.join(framesRoot, entry.slug);
  const manifestPath = path.join(componentDirectory, 'frames.json');
  const previous = await existingCapture(manifestPath);
  if (previous && !overwrite) {
    if (previous.slug !== entry.slug || !Array.isArray(previous.frames) || previous.frames.length < 2) {
      throw new Error('Existing capture is incomplete; use overwrite explicitly: ' + manifestPath);
    }
    return { slug: entry.slug, status: 'already-recorded', frameCount: previous.frames.length, manifest: manifestPath };
  }
  const takeName = 'take-' + Date.now() + '-' + Math.random().toString(16).slice(2, 8);
  const takeDirectory = path.join(componentDirectory, takeName);
  await fs.mkdir(takeDirectory, { recursive: true });
  await page.goto(pathToFileURL(path.join(repo, entry.preview)).href);
  await page.waitForSelector('#demo-stage', { state: 'visible' });
  await page.waitForLoadState();
  if (entry.kind === 'html') {
    await page.evaluate(height => {
      document.querySelector('#demo-stage').style.minHeight = height + 'px';
    }, Math.ceil(entry.canvas[1]));
  }
  if (entry.slug !== 'wechat-svg-drawline') {
    await page.evaluate(async () => {
      await Promise.all([...document.querySelectorAll('#demo-stage img, #demo-stage image')].map(async element => {
        const source = element.getAttribute('src') || element.getAttribute('href') || element.getAttribute('xlink:href');
        if (!source) return;
        const image = new Image();
        image.src = source;
        await image.decode();
      }));
    });
  }
  const bounds = await stageBounds(page);
  if (bounds.overflow || bounds.height <= 0 || bounds.height > 1200 || Math.abs(bounds.x) > 0.5 || Math.abs(bounds.y) > 0.5 || Math.abs(bounds.width - 600) > 0.5 || bounds.scrollX || bounds.scrollY) {
    throw new Error('Unexpected capture geometry ' + entry.slug + ': ' + JSON.stringify(bounds));
  }
  const clip = { x: 0, y: 0, width: 600, height: Math.ceil(bounds.height) };
  const frames = [], actions = [];
  const origin = performance.now();
  let lastFrame = -Infinity, mouseHeld = false;
  const seconds = () => Number(((performance.now() - origin) / 1000).toFixed(6));

  async function captureFrame() {
    const remaining = lastFrame + INTERVAL_MS - performance.now();
    if (remaining > 0) await sleep(remaining);
    if (frames.length % 8 === 0) {
      const current = await stageBounds(page);
      if (current.overflow || Math.abs(current.width - bounds.width) > 0.5 || Math.abs(current.height - bounds.height) > 0.5 || Math.abs(current.x) > 0.5 || Math.abs(current.y) > 0.5) {
        throw new Error('Capture dimensions changed ' + entry.slug);
      }
    }
    const filename = 'frame' + String(frames.length + 1).padStart(4, '0') + '.png';
    const timestamp = seconds();
    lastFrame = performance.now();
    // Fast PNG capture avoids the wrapper's DPR pass during a continuous recording.
    const screenshot = await page.cdp('Page.captureScreenshot', {
      format: 'png', clip: { ...clip, scale: 1 },
      captureBeyondViewport: false, optimizeForSpeed: true,
    });
    await fs.writeFile(path.join(takeDirectory, filename), Buffer.from(screenshot.data, 'base64'));
    frames.push({ file: takeName + '/' + filename, time: timestamp });
  }

  async function captureFor(duration) {
    const finish = performance.now() + duration * 1000;
    do {
      await captureFrame();
    } while (performance.now() < finish);
  }

  async function pointFor(selector) {
    const deadline = performance.now() + 3500;
    do {
      const point = await actionablePoint(page, selector);
      if (point) return point;
      await captureFrame();
    } while (performance.now() < deadline);
    throw new Error('No visible enabled target for ' + entry.slug + ': ' + selector);
  }

  try {
    if (entry.slug !== 'wechat-svg-drawline') await captureFor(0.55);
    for (const step of PLANS[entry.slug]) {
      if (step.type === 'auto') {
        actions.push({ time: seconds(), action: 'observe-autoplay' });
        await captureFor(step.seconds);
        continue;
      }
      const point = await pointFor(step.selector);
      if (step.type === 'click') {
        await page.mouse.click(point.x, point.y, { label: '演示组件点击效果' });
        actions.push({ time: seconds(), action: 'click', selector: step.selector, ...point });
        await captureFor(step.seconds);
      } else if (step.type === 'hold') {
        await page.mouse.move(point.x, point.y, { label: '按住组件查看效果' });
        await page.mouse.down();
        mouseHeld = true;
        actions.push({ time: seconds(), action: 'mouse-down', selector: step.selector, ...point });
        try {
          await captureFor(step.seconds);
        } finally {
          await page.mouse.up();
          mouseHeld = false;
          actions.push({ time: seconds(), action: 'mouse-up' });
        }
        await captureFor(step.release);
      } else if (step.type === 'wheel') {
        await page.mouse.move(point.x, point.y, { label: '定位组件滚动区域' });
        await page.mouse.wheel(step.deltaX, step.deltaY, { label: '演示组件滚动效果' });
        actions.push({ time: seconds(), action: 'wheel', selector: step.selector, deltaX: step.deltaX, deltaY: step.deltaY, ...point });
        await captureFor(step.seconds);
      }
    }
    await captureFor(0.6);
    for (const file of dependencies) {
      if (createHash('sha256').update(await fs.readFile(path.join(exampleDirectory, file))).digest('hex') !== sourceHashes[file]) throw new Error('Demo source changed during capture: ' + file);
    }
    const record = { slug: entry.slug, width: clip.width, height: clip.height, frames, actions,
      source_sha256: sourceHashes,
      source: 'browser-capture', completed: true, targetFps: 8,
      play: entry.kind === 'workflow' ? 'operation-illustration' : 'component-demo' };
    const staged = path.join(componentDirectory, '.frames-' + takeName + '.json');
    await fs.writeFile(staged, JSON.stringify(record, null, 2) + '\n', 'utf8');
    if (overwrite) await fs.rename(staged, manifestPath);
    else {
      await fs.link(staged, manifestPath);
      await fs.unlink(staged);
    }
    return { slug: entry.slug, status: 'recorded', frameCount: frames.length,
      duration: frames.at(-1).time - frames[0].time, manifest: manifestPath };
  } catch (error) {
    await fs.writeFile(path.join(takeDirectory, 'capture-error.json'), JSON.stringify({
      slug: entry.slug, completed: false, frames, actions, error: String(error),
    }, null, 2) + '\n', 'utf8');
    throw error;
  } finally {
    if (mouseHeld) {
      try { await page.mouse.up(); } catch { /* The parent owns recovery if the page closed. */ }
    }
  }
}

export async function recordBatch(page, slugs, options = {}) {
  const repo = path.resolve(options.repo || DEFAULT_REPO);
  const framesRoot = path.resolve(options.framesRoot || path.join(repo, 'output/brand-gif-frames'));
  const manifest = JSON.parse(await fs.readFile(path.join(repo, 'assets/brand/demo-manifest.json'), 'utf8'));
  if (!Array.isArray(manifest) || manifest.length === 0 || new Set(manifest.map(entry => entry.slug)).size !== manifest.length) {
    throw new Error('Expected a nonempty manifest with unique component names');
  }
  const selected = slugs ?? manifest.map(entry => entry.slug);
  if (!Array.isArray(selected) || selected.length === 0 || new Set(selected).size !== selected.length) {
    throw new Error('slugs must be a nonempty array of unique component names');
  }
  const entries = selected.map(slug => {
    const entry = manifest.find(candidate => candidate.slug === slug);
    if (!entry || !PLANS[slug]) throw new Error('Unknown demo ' + slug);
    return entry;
  });
  await page.cdp('Emulation.setDeviceMetricsOverride', { width: 600, height: 1200, deviceScaleFactor: 1, mobile: false });
  const results = [];
  for (const entry of entries) {
    const result = await recordOne(page, entry, repo, framesRoot, Boolean(options.overwrite));
    results.push(result);
    console.log({ capture: result });
  }
  return { recorded: results.filter(result => result.status === 'recorded').length,
    results, snapshot: await page.snapshot() };
}

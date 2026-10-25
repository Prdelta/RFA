#!/usr/bin/env node
/**
 * capture_page.js — capture the evidence needed to reverse engineer a frontend.
 *
 * Usage:
 *   node capture_page.js <url|file.html> --out <dir> [options]
 *
 * Options:
 *   --viewport WxH        Viewport, repeatable (default 1440x900). Each viewport
 *                         gets its own sub-directory in --out.
 *   --full-page           Screenshot the whole scrollable page.
 *   --selector <css>      Limit computed styles + screenshot to one subtree.
 *   --hover <css>         Hover this element before capturing.
 *   --focus <css>         Focus this element (keyboard focus ring state) before capturing.
 *   --click <css>         Click this element before capturing (opens menus, modals).
 *   --scroll-to <css|px>  Scroll to an element or a pixel offset before capturing.
 *   --wait <ms>           Extra wait after load (default 1500).
 *   --wait-for <css>      Wait until this selector is visible before capturing.
 *   --dark                Emulate prefers-color-scheme: dark.
 *   --reduced-motion      Emulate prefers-reduced-motion: reduce.
 *   --user-agent <ua>     Custom user agent (mobile sites, bot-detection checks).
 *   --locale <tag>        Browser locale, e.g. es-ES.
 *   --cdp <url>           Attach to a running Chromium/Electron over CDP instead of
 *                         launching (e.g. http://127.0.0.1:9222). Uses the first
 *                         open page whose URL contains <target>, or the first page.
 *   --proxy <url>         Route the browser through this proxy (http://host:port).
 *   --proxy-from-env      Use HTTPS_PROXY/HTTP_PROXY from the environment.
 *   --ignore-https-errors Trust the proxy's intercepting certificate (only needed
 *                         behind a TLS-terminating proxy you control).
 *   --autoscroll          Scroll the whole page before capturing to trigger lazy
 *                         images and scroll-reveal animations, then return to top.
 *   --dismiss             Best-effort close of cookie/consent banners and full-screen
 *                         overlays before capturing (OneTrust, Cookiebot, Didomi,
 *                         and buttons matching accept/aceptar/agree/got it).
 *   --dismiss-selector <css>  Also click this selector to dismiss an overlay.
 *   --storage-state <f>   Playwright storage state JSON (cookies/localStorage) for
 *                         logged-in captures the user produced themselves.
 *   --executable-path <p> Use an existing Chromium binary.
 *   --max-elements <n>    Cap on elements with computed styles (default 3000).
 *   --no-har              Skip the network inventory.
 *   --headed              Show the browser.
 *
 * Output per viewport directory:
 *   capture.json   DOM summary, computed styles, custom properties, fonts,
 *                  animations, breakpoints, framework hints, network inventory
 *   screenshot.png
 *   dom.html       Serialized DOM after load (not the original HTML)
 *   styles/        Every same-origin or CORS-readable stylesheet text
 *   har.json       Lightweight request inventory (url, type, status, size)
 *
 * Nothing is executed beyond loading the page in a real browser; no form is
 * submitted and no credentials are read from the user's profile.
 */
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = { viewports: [], wait: 1500, maxElements: 3000, har: true };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case '--out': args.out = next(); break;
      case '--viewport': args.viewports.push(next()); break;
      case '--full-page': args.fullPage = true; break;
      case '--selector': args.selector = next(); break;
      case '--hover': args.hover = next(); break;
      case '--focus': args.focus = next(); break;
      case '--wait-for': args.waitFor = next(); break;
      case '--dark': args.dark = true; break;
      case '--reduced-motion': args.reducedMotion = true; break;
      case '--user-agent': args.userAgent = next(); break;
      case '--locale': args.locale = next(); break;
      case '--cdp': args.cdp = next(); break;
      case '--proxy': args.proxy = next(); break;
      case '--proxy-from-env': args.proxy = process.env.HTTPS_PROXY || process.env.https_proxy || process.env.HTTP_PROXY || null; break;
      case '--ignore-https-errors': args.ignoreHttpsErrors = true; break;
      case '--autoscroll': args.autoscroll = true; break;
      case '--dismiss': args.dismiss = true; break;
      case '--dismiss-selector': args.dismissSel = next(); break;
      case '--click': args.click = next(); break;
      case '--scroll-to': args.scrollTo = next(); break;
      case '--wait': args.wait = Number(next()); break;
      case '--storage-state': args.storageState = next(); break;
      case '--executable-path': args.executablePath = next(); break;
      case '--max-elements': args.maxElements = Number(next()); break;
      case '--no-har': args.har = false; break;
      case '--headed': args.headed = true; break;
      case '--help': case '-h': args.help = true; break;
      default: rest.push(a);
    }
  }
  args.target = rest[0];
  if (args.viewports.length === 0) args.viewports.push('1440x900');
  return args;
}

function loadPlaywright(args) {
  try {
    return require('playwright');
  } catch (e) {
    try { return require('playwright-core'); } catch (_) {}
    console.error('playwright is not installed. Run: npm i playwright && npx playwright install chromium');
    console.error('or pass --executable-path to an existing Chromium with playwright-core.');
    process.exit(2);
  }
}

function toUrl(target) {
  if (/^https?:\/\//i.test(target) || /^file:\/\//i.test(target)) return target;
  const abs = path.resolve(target);
  if (fs.existsSync(abs)) return 'file://' + abs;
  return 'https://' + target;
}

// Runs inside the page. Keep it self-contained: no closures over Node scope.
function collectInPage(opts) {
  const { selector, maxElements } = opts;
  const root = selector ? document.querySelector(selector) : document.documentElement;
  if (!root) return { error: 'selector not found: ' + selector };

  const STYLE_PROPS = [
    'display','position','top','right','bottom','left','z-index','float','clear',
    'width','height','min-width','max-width','min-height','max-height','box-sizing',
    'margin-top','margin-right','margin-bottom','margin-left',
    'padding-top','padding-right','padding-bottom','padding-left',
    'flex-direction','flex-wrap','justify-content','align-items','align-content','gap','row-gap','column-gap','flex-grow','flex-shrink','flex-basis','order',
    'grid-template-columns','grid-template-rows','grid-auto-flow','grid-column','grid-row',
    'font-family','font-size','font-weight','font-style','line-height','letter-spacing','text-transform','text-align','text-decoration-line','white-space','word-break',
    'color','background-color','background-image','background-size','background-position','background-repeat',
    'border-top-width','border-top-style','border-top-color','border-right-width','border-bottom-width','border-left-width','border-color','border-style',
    'border-top-left-radius','border-top-right-radius','border-bottom-right-radius','border-bottom-left-radius',
    'box-shadow','opacity','overflow-x','overflow-y','cursor','pointer-events','visibility',
    'transform','transform-origin','transition-property','transition-duration','transition-timing-function','transition-delay',
    'animation-name','animation-duration','animation-timing-function','animation-iteration-count','animation-delay',
    'backdrop-filter','filter','object-fit','aspect-ratio','outline-style','outline-width','outline-color','outline-offset',
    'animation-timeline','animation-range-start','animation-range-end','view-transition-name','container-type','container-name','content-visibility','scroll-snap-type','scroll-snap-align','color-scheme','mix-blend-mode','clip-path',
  ];

  const nodes = [];
  const idByEl = new Map();
  const shadowRoots = [];   // open shadow roots found while walking (web components)
  let idx = 0;
  const stack = [{ el: root, parentId: null, inShadow: false }];
  while (stack.length && nodes.length < maxElements) {
    const { el, parentId, inShadow } = stack.pop();
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    let myId = parentId;
    if (visible || el === root) {
      const styles = {};
      for (const p of STYLE_PROPS) styles[p] = cs.getPropertyValue(p);
      const pseudo = {};
      for (const ps of ['::before', '::after']) {
        const pcs = getComputedStyle(el, ps);
        if (pcs.content && pcs.content !== 'none' && pcs.content !== 'normal') {
          pseudo[ps] = { content: pcs.content, color: pcs.color, 'background-color': pcs.backgroundColor, width: pcs.width, height: pcs.height };
        }
      }
      const id = idx++;
      idByEl.set(el, id); myId = id;
      let text = '';
      for (const c of el.childNodes) if (c.nodeType === 3) text += c.textContent;
      text = text.replace(/\s+/g, ' ').trim().slice(0, 120);
      const attrs = {};
      for (const a of el.attributes) {
        if (['class','id','role','href','src','alt','type','name','placeholder','tabindex','popover','open','is','slot','part','exportparts'].includes(a.name) || a.name.startsWith('aria-') || a.name.startsWith('data-')) attrs[a.name] = a.value.slice(0, 200);
      }
      const tag = el.tagName.toLowerCase();
      nodes.push({
        id, parent: parentId, tag, attrs, text,
        custom: tag.includes('-') || undefined, shadow: inShadow || undefined, shadowHost: el.shadowRoot ? true : undefined,
        rect: { x: Math.round(rect.x), y: Math.round(rect.y + window.scrollY), w: Math.round(rect.width), h: Math.round(rect.height) },
        styles, pseudo: Object.keys(pseudo).length ? pseudo : undefined,
      });
    }
    const kids = [];
    for (const c of el.children) kids.push({ el: c, parentId: myId, inShadow });
    if (el.shadowRoot) { shadowRoots.push(el.shadowRoot); for (const c of el.shadowRoot.children) kids.push({ el: c, parentId: myId, inShadow: true }); }
    for (let i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);   // DFS, document order
  }

  // CSS custom properties, keyframes, media + container queries, font-faces — including shadow roots.
  const customProps = {};
  const keyframes = {};
  const mediaQueries = {};
  const containerQueries = {};
  const fontFaces = [];
  const sheetsInfo = [];
  const visit = (ruleList, media, info) => {
    for (const r of ruleList) {
      info.rules++;
      if (r.type === CSSRule.STYLE_RULE) {
        for (const name of r.style) if (name.startsWith('--')) {
          const v = r.style.getPropertyValue(name).trim();
          customProps[name] = customProps[name] || [];
          if (customProps[name].length < 8) customProps[name].push({ value: v, selector: (r.selectorText || '').slice(0, 120), media });
        }
      } else if (r.type === CSSRule.KEYFRAMES_RULE) {
        keyframes[r.name] = Array.from(r.cssRules).map(k => ({ key: k.keyText, style: k.style.cssText.slice(0, 500) }));
      } else if (r.type === CSSRule.MEDIA_RULE) {
        const q = r.media.mediaText; mediaQueries[q] = (mediaQueries[q] || 0) + r.cssRules.length; visit(r.cssRules, q, info);
      } else if (r.type === CSSRule.FONT_FACE_RULE) {
        fontFaces.push({ family: r.style.getPropertyValue('font-family'), weight: r.style.getPropertyValue('font-weight'), style: r.style.getPropertyValue('font-style'), src: r.style.getPropertyValue('src').slice(0, 300), display: r.style.getPropertyValue('font-display') });
      } else if (r.cssRules && r.constructor && /ContainerRule/.test(r.constructor.name)) {
        const q = ((r.containerName ? r.containerName + ' ' : '') + (r.containerQuery || r.conditionText || '')).trim() || '(container)'; containerQueries[q] = (containerQueries[q] || 0) + r.cssRules.length; visit(r.cssRules, media, info);
      } else if (r.cssRules) {
        visit(r.cssRules, media, info);
      }
    }
  };
  for (const sheet of document.styleSheets) {
    const info = { href: sheet.href, readable: true, rules: 0 };
    let rules; try { rules = sheet.cssRules; } catch (e) { info.readable = false; sheetsInfo.push(info); continue; }
    visit(rules, null, info); sheetsInfo.push(info);
  }
  let shadowSheets = 0;
  for (const sr of shadowRoots) {
    try {
      const sheets = Array.from(sr.adoptedStyleSheets || []);
      for (const st of sr.querySelectorAll('style')) { try { if (st.sheet) sheets.push(st.sheet); } catch (e) {} }
      for (const st of sheets) { try { const info = { href: 'shadow', readable: true, rules: 0 }; visit(st.cssRules, 'shadow', info); sheetsInfo.push(info); shadowSheets++; } catch (e) {} }
    } catch (e) {}
  }
  // Resolved values on :root for every custom property we found.
  const rootCs = getComputedStyle(document.documentElement);
  const resolvedRoot = {};
  for (const k of Object.keys(customProps)) { const v = rootCs.getPropertyValue(k).trim(); if (v) resolvedRoot[k] = v; }

  const loadedFonts = [];
  try { for (const f of document.fonts) loadedFonts.push({ family: f.family, weight: f.weight, style: f.style, status: f.status }); } catch (e) {}

  // Framework and library hints visible from the DOM/global scope.
  const g = window;
  const hints = {
    react: !!(g.React || document.querySelector('[data-reactroot], [data-reactid]') || Object.keys(document.body || {}).some(k => k.startsWith('__reactFiber') || k.startsWith('__reactContainer')) || !!g.__REACT_DEVTOOLS_GLOBAL_HOOK__),
    nextjs: !!(g.__NEXT_DATA__ || g.next || document.querySelector('#__next, script#__NEXT_DATA__')),
    vue: !!(g.Vue || g.__VUE__ || document.querySelector('[data-v-app], [data-server-rendered]') || Array.from(document.querySelectorAll('*')).slice(0, 2000).some(e => e.__vue__ || e.__vue_app__)),
    nuxt: !!(g.__NUXT__ || document.querySelector('#__nuxt')),
    angular: !!(g.ng || g.getAllAngularRootElements || document.querySelector('[ng-version]')),
    svelte: !!(document.querySelector('[class*="svelte-"]') || g.__svelte),
    sveltekit: !!(g.__sveltekit_dev || document.querySelector('[data-sveltekit-preload-data]')),
    astro: !!document.querySelector('astro-island, [data-astro-cid], astro-slot'),
    remix: !!(g.__remixContext || g.__remixManifest),
    gatsby: !!(g.___gatsby || document.querySelector('#___gatsby')),
    jquery: !!(g.jQuery || g.$ && g.$.fn),
    tailwind: (() => { const re = /(^|\s)((px|py|pt|pb|pl|pr|mt|mb|mx|my|gap|space-x|space-y)-\d+|(sm|md|lg|xl|2xl):[a-z-]+|text-(xs|sm|base|lg|xl|\dxl)|(bg|text|border)-[a-z]+-\d{2,3}|rounded-(sm|md|lg|xl|full)|font-(semibold|bold|medium))(\s|$)/; let n = 0; for (const e of Array.from(document.querySelectorAll('[class]')).slice(0, 2000)) { const c = typeof e.className === 'string' ? e.className : ''; if (re.test(c) && ++n >= 3) return true; } return false; })(),
    styledComponents: !!document.querySelector('style[data-styled], [class*="sc-"]'),
    emotion: !!document.querySelector('style[data-emotion], [class^="css-"]'),
    cssModules: Array.from(document.querySelectorAll('[class]')).slice(0, 1500).some(e => /[A-Za-z]+_[A-Za-z]+__[A-Za-z0-9]{5,}/.test(typeof e.className === 'string' ? e.className : '')),
    bootstrap: !!(g.bootstrap || document.querySelector('.container .row > [class*="col-"], .navbar-expand-lg, [data-bs-toggle]')),
    mui: !!document.querySelector('[class*="MuiButton"], [class*="MuiBox"], [class*="MuiTypography"]'),
    chakra: !!document.querySelector('[class*="chakra-"]'),
    radix: !!document.querySelector('[data-radix-popper-content-wrapper], [data-radix-collection-item], [data-state][data-orientation]'),
    shadcn: !!document.querySelector('[data-slot], [cmdk-root]'),
    antd: !!document.querySelector('[class*="ant-btn"], [class*="ant-layout"]'),
    framerMotion: !!document.querySelector('[style*="transform: translate"][style*="opacity"], [data-framer-name], [data-framer-component-type]'),
    gsap: !!(g.gsap || g.TweenMax),
    lottie: !!(g.lottie || document.querySelector('lottie-player, [data-lottie]')),
    threejs: !!(g.THREE || document.querySelector('canvas[data-engine*="three"]')),
    webflow: !!(g.Webflow || document.querySelector('html[data-wf-site]')),
    wordpress: !!document.querySelector('link[href*="wp-content"], meta[name="generator"][content*="WordPress"]'),
    shopify: !!(g.Shopify || document.querySelector('link[href*="cdn.shopify.com"]')),
    squarespace: !!document.querySelector('meta[name="generator"][content*="Squarespace"]'),
    wix: !!document.querySelector('meta[name="generator"][content*="Wix"]'),
    framer: !!document.querySelector('meta[name="generator"][content*="Framer"]'),
  };
  const generator = document.querySelector('meta[name="generator"]');

  const scripts = Array.from(document.scripts).map(s => ({ src: s.src || null, type: s.type || null, module: s.type === 'module', inlineBytes: s.src ? 0 : (s.textContent || '').length })).slice(0, 300);
  const links = Array.from(document.querySelectorAll('link[rel]')).map(l => ({ rel: l.rel, href: l.href, as: l.as || null })).slice(0, 300);
  const icons = {
    svgInline: document.querySelectorAll('svg').length,
    svgSymbols: document.querySelectorAll('svg use').length,
    imgs: document.querySelectorAll('img').length,
    iconFonts: Array.from(document.styleSheets).some(s => s.href && /fontawesome|font-awesome|material-icons|icomoon/i.test(s.href)),
  };

  return {
    url: location.href, title: document.title, lang: document.documentElement.lang || null,
    viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio }, documentSize: { w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight },
    theme: { colorScheme: rootCs.colorScheme, dataTheme: document.documentElement.dataset.theme || null, htmlClass: document.documentElement.className || null, prefersDark: matchMedia('(prefers-color-scheme: dark)').matches },
    generator: generator ? generator.content : null,
    frameworkHints: hints,
    stylesheets: sheetsInfo, customProperties: customProps, customPropertiesRoot: resolvedRoot,
    keyframes, mediaQueries, containerQueries, fontFaces, loadedFonts, scripts, links, icons,
    shadow: { hosts: shadowRoots.length, styleSheets: shadowSheets, nodes: nodes.filter(n => n.shadow).length },
    customElements: Array.from(new Set(nodes.filter(n => n.custom).map(n => n.tag))).slice(0, 40),
    nodeCount: nodes.length, truncated: nodes.length >= maxElements, nodes,
  };
}

async function captureStylesheetTexts(page, outDir) {
  const dir = path.join(outDir, 'styles'); fs.mkdirSync(dir, { recursive: true });
  const sheets = await page.evaluate(() => Array.from(document.styleSheets).map(s => s.href).filter(Boolean));
  const inline = await page.evaluate(() => Array.from(document.querySelectorAll('style')).map(s => s.textContent || ''));
  inline.forEach((t, i) => fs.writeFileSync(path.join(dir, `inline-${i}.css`), t));
  const saved = [];
  for (let i = 0; i < sheets.length; i++) {
    try {
      const txt = await page.evaluate(async (href) => { const r = await fetch(href, { mode: 'cors' }); return r.ok ? await r.text() : null; }, sheets[i]);
      if (txt != null) { const name = `sheet-${i}-${path.basename(new URL(sheets[i]).pathname).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 60) || 'style.css'}`; fs.writeFileSync(path.join(dir, name), txt); saved.push({ href: sheets[i], file: name, bytes: txt.length }); }
      else saved.push({ href: sheets[i], file: null, reason: 'fetch failed or blocked' });
    } catch (e) { saved.push({ href: sheets[i], file: null, reason: String(e).slice(0, 120) }); }
  }
  return saved;
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.target || !args.out) {
    console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0].replace(/^\/\*\*\s*/, '').replace(/^ \* ?/gm, ''));
    process.exit(args.help ? 0 : 1);
  }
  const { chromium } = loadPlaywright(args);
  const url = toUrl(args.target);
  const browser = args.cdp ? await chromium.connectOverCDP(args.cdp) : await chromium.launch({ headless: !args.headed, executablePath: args.executablePath || undefined, proxy: args.proxy ? { server: args.proxy } : undefined, args: args.ignoreHttpsErrors ? ['--ignore-certificate-errors'] : [] });
  const summary = { target: url, capturedAt: new Date().toISOString(), mode: args.cdp ? 'attached over CDP' : 'launched', emulation: { dark: !!args.dark, reducedMotion: !!args.reducedMotion }, viewports: [] };
  try {
    for (const vp of args.viewports) {
      const [w, h] = vp.split('x').map(Number);
      const outDir = path.join(args.out, `${w}x${h}`); fs.mkdirSync(outDir, { recursive: true });
      let context, page, attached = false;
      if (args.cdp) {
        context = browser.contexts()[0] || await browser.newContext();
        const pages = context.pages();
        page = pages.find(p => p.url().includes(args.target)) || pages[0];
        if (page) { attached = true; try { await page.setViewportSize({ width: w, height: h }); } catch (e) {} }
        else page = await context.newPage();
      } else {
        context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, storageState: args.storageState || undefined, userAgent: args.userAgent || undefined, locale: args.locale || undefined, colorScheme: args.dark ? 'dark' : undefined, reducedMotion: args.reducedMotion ? 'reduce' : undefined, ignoreHTTPSErrors: !!args.ignoreHttpsErrors });
      }
      const requests = [];
      if (args.har) context.on('response', async (res) => {
        try { const req = res.request(); const hdr = res.headers(); requests.push({ url: res.url().slice(0, 500), method: req.method(), status: res.status(), type: req.resourceType(), contentType: hdr['content-type'] || null, size: Number(hdr['content-length'] || 0) || null }); } catch (e) {}
      });
      if (!page) page = await context.newPage();
      if (args.cdp && (args.dark || args.reducedMotion)) await page.emulateMedia({ colorScheme: args.dark ? 'dark' : undefined, reducedMotion: args.reducedMotion ? 'reduce' : undefined });
      const consoleErrors = [];
      page.on('pageerror', e => consoleErrors.push(String(e).slice(0, 300)));
      if (!attached) {
        await page.goto(url, { waitUntil: 'load', timeout: 60000 });
        try { await page.waitForLoadState('networkidle', { timeout: 10000 }); } catch (e) {}
      }
      if (args.waitFor) await page.locator(args.waitFor).first().waitFor({ state: 'visible', timeout: 30000 });
      await page.waitForTimeout(args.wait);
      const dismissed = [];
      if (args.dismiss || args.dismissSel) {
        if (args.dismissSel) { try { await page.locator(args.dismissSel).first().click({ timeout: 2500 }); dismissed.push(args.dismissSel); } catch (e) {} }
        const SEL = ['#onetrust-accept-btn-handler', '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll', '#CybotCookiebotDialogBodyButtonAccept', '.cc-allow', '.cookie-accept', '[data-testid="uc-accept-all-button"]', '#didomi-notice-agree-button', '.qc-cmp2-summary-buttons button[mode="primary"]', 'button[aria-label*="accept" i]', 'button[aria-label*="consent" i]'];
        for (const s of SEL) { try { const el = page.locator(s).first(); if (await el.count() && await el.isVisible()) { await el.click({ timeout: 2000 }); dismissed.push(s); break; } } catch (e) {} }
        try { const byText = await page.evaluate(() => { const re = /^(accept all|accept|aceptar|agree|got it|entendido|allow all|i agree|consent|acepto|aceptar todo)$/i; for (const b of Array.from(document.querySelectorAll('button, a[role=button], [role=button]'))) { const tx = (b.textContent || '').trim(); if (re.test(tx)) { b.click(); return tx; } } return null; }); if (byText) dismissed.push('text:' + byText); } catch (e) {}
        // remove any remaining full-viewport fixed overlay with a high z-index
        try { const removed = await page.evaluate(() => { let n = 0; for (const el of Array.from(document.querySelectorAll('body *'))) { const cs = getComputedStyle(el); const r = el.getBoundingClientRect(); if ((cs.position === 'fixed' || cs.position === 'sticky') && +cs.zIndex >= 1000 && r.width >= innerWidth * 0.9 && r.height >= innerHeight * 0.6 && cs.display !== 'none') { el.style.display = 'none'; n++; } } document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto'; return n; }); if (removed) dismissed.push('overlays:' + removed); } catch (e) {}
        await page.waitForTimeout(500);
      }
      if (args.autoscroll) {
        await page.evaluate(async () => { const h = document.documentElement; const step = Math.max(400, innerHeight * 0.9); for (let y = 0; y <= h.scrollHeight; y += step) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); } window.scrollTo(0, 0); await new Promise(r => setTimeout(r, 300)); });
      }
      const stateActions = [];
      if (dismissed.length) stateActions.push('dismissed ' + dismissed.join(', '));
      if (args.autoscroll) stateActions.push('autoscroll');
      if (args.dark) stateActions.push('emulate dark'); if (args.reducedMotion) stateActions.push('emulate reduced-motion');
      if (args.scrollTo) { if (/^\d+$/.test(args.scrollTo)) await page.evaluate(y => window.scrollTo(0, y), Number(args.scrollTo)); else await page.locator(args.scrollTo).first().scrollIntoViewIfNeeded(); stateActions.push('scroll-to ' + args.scrollTo); await page.waitForTimeout(600); }
      if (args.hover) { await page.locator(args.hover).first().hover(); stateActions.push('hover ' + args.hover); await page.waitForTimeout(600); }
      if (args.focus) { await page.locator(args.focus).first().focus(); await page.keyboard.press('Shift'); stateActions.push('focus ' + args.focus); await page.waitForTimeout(300); }
      if (args.click) { await page.locator(args.click).first().click(); stateActions.push('click ' + args.click); await page.waitForTimeout(800); }
      const data = await page.evaluate(collectInPage, { selector: args.selector || null, maxElements: args.maxElements });
      if (data.error) throw new Error(data.error);
      data.stateActions = stateActions; data.consoleErrors = consoleErrors;
      data.stylesheetFiles = await captureStylesheetTexts(page, outDir);
      if (args.selector) await page.locator(args.selector).first().screenshot({ path: path.join(outDir, 'screenshot.png') });
      else await page.screenshot({ path: path.join(outDir, 'screenshot.png'), fullPage: !!args.fullPage });
      fs.writeFileSync(path.join(outDir, 'dom.html'), await page.content());
      if (args.har) { fs.writeFileSync(path.join(outDir, 'har.json'), JSON.stringify({ requests }, null, 1)); data.network = { count: requests.length, byType: requests.reduce((m, r) => (m[r.type] = (m[r.type] || 0) + 1, m), {}), thirdPartyHosts: Array.from(new Set(requests.map(r => { try { return new URL(r.url).host; } catch (e) { return null; } }).filter(hst => hst && hst !== new URL(url.startsWith('file:') ? 'http://localfile' : url).host))).slice(0, 60) }; }
      fs.writeFileSync(path.join(outDir, 'capture.json'), JSON.stringify(data, null, 1));
      summary.viewports.push({ viewport: vp, dir: outDir, nodes: data.nodeCount, truncated: data.truncated, title: data.title, frameworkHints: Object.entries(data.frameworkHints).filter(([, v]) => v).map(([k]) => k), fonts: Array.from(new Set(data.loadedFonts.map(f => f.family))), customProperties: Object.keys(data.customProperties).length, keyframes: Object.keys(data.keyframes).length, mediaQueries: Object.keys(data.mediaQueries).length, containerQueries: Object.keys(data.containerQueries).length, shadowHosts: data.shadow.hosts, shadowNodes: data.shadow.nodes, customElements: data.customElements.length, consoleErrors: consoleErrors.length });
      if (!args.cdp) await context.close();
    }
  } finally { if (args.cdp) { try { await browser.close(); } catch (e) {} } else await browser.close(); }
  fs.writeFileSync(path.join(args.out, 'summary.json'), JSON.stringify(summary, null, 1));
  console.log(JSON.stringify(summary, null, 1));
}

run().catch(e => { console.error('capture failed:', e.message || e); process.exit(1); });

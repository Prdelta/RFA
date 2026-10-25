#!/usr/bin/env python3
"""detect_stack.py - fingerprint the frontend stack of a URL, a saved HTML file,
or a capture directory produced by capture_page.js.

Usage:
    python3 detect_stack.py <url | file.html | capture-dir> [--json] [--max-scripts N]

It downloads the HTML and the first N external scripts/stylesheets (default 12),
then matches signatures for frameworks, meta-frameworks, CSS strategies, UI
libraries, bundlers, motion libraries, site builders and analytics. Each claim
comes with the evidence string that matched and a confidence (high/medium/low).
Nothing is executed. Uses only the standard library.
"""
import json, os, re, sys, urllib.request, urllib.parse, html as htmlmod

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 reverse-engineer-frontend/1"

# (category, name, regex on HTML, regex on script/css text, confidence)
SIGNATURES = [
    ("framework", "React", r'data-reactroot|__reactFiber|react-dom|data-reactid', r'__reactInternalInstance|react\.production\.min|createElement\(|__REACT_DEVTOOLS_GLOBAL_HOOK__|"react-dom"', "high"),
    ("framework", "Preact", r'', r'preact\b|__preactattr_', "medium"),
    ("framework", "Vue", r'data-v-[0-9a-f]{6,}|data-server-rendered|id="app"[^>]*data-v-app|__vue', r'__VUE_DEVTOOLS_GLOBAL_HOOK__|Vue\.config|createApp\(|__vue_app__', "high"),
    ("framework", "Angular", r'ng-version=|_nghost-|_ngcontent-|ng-app', r'platformBrowserDynamic|ɵɵ|@angular/core', "high"),
    ("framework", "Svelte", r'class="[^"]*svelte-[a-z0-9]{4,}', r'svelte/internal|\.svelte-[a-z0-9]{4,}\{', "high"),
    ("framework", "SolidJS", r'', r'solid-js|_\$HY|\$\$click', "medium"),
    ("framework", "Alpine.js", r'x-data=|x-show=|x-bind:', r'alpinejs|Alpine\.start', "high"),
    ("framework", "htmx", r'hx-get=|hx-post=|hx-swap=', r'htmx\.org|htmx\.process', "high"),
    ("framework", "jQuery", r'', r'jQuery\.fn\.jquery|jquery(\.min)?\.js|\$\.fn\.jquery', "medium"),
    ("framework", "Lit / Web Components", r'<[a-z]+-[a-z-]+[^>]*>', r'lit-element|lit-html|customElements\.define', "low"),
    ("meta-framework", "Next.js", r'__NEXT_DATA__|/_next/static/|id="__next"', r'__NEXT_DATA__|/_next/static|next/dist', "high"),
    ("meta-framework", "Nuxt", r'id="__nuxt"|__NUXT__|/_nuxt/', r'__NUXT__|/_nuxt/', "high"),
    ("meta-framework", "Remix", r'__remixContext|/build/_shared/|data-remix', r'__remixContext|__remixManifest', "high"),
    ("meta-framework", "Gatsby", r'id="___gatsby"|/page-data/|gatsby-', r'___gatsby|gatsby-browser', "high"),
    ("meta-framework", "Astro", r'<astro-island|data-astro-cid|astro-slot|/_astro/', r'astro:|/_astro/', "high"),
    ("meta-framework", "SvelteKit", r'data-sveltekit-preload|/_app/immutable/', r'__sveltekit|_app/immutable', "high"),
    ("meta-framework", "Qwik", r'q:container|q:version', r'qwikloader', "high"),
    ("meta-framework", "Docusaurus", r'docusaurus', r'docusaurus', "high"),
    ("meta-framework", "Vite (dev or build)", r'/@vite/client|type="module" crossorigin src="/assets/index-[a-zA-Z0-9_-]+\.js"', r'__vite__|vite/modulepreload-polyfill|__vitePreload', "medium"),
    ("css", "Tailwind CSS v4", r'', r'@layer theme, ?base, ?components, ?utilities|@property --tw-|--tw-sort:|color-mix\(in oklab', "high"),
    ("css", "Tailwind CSS", r'class="[^"]*\b((px|py|pt|pb|pl|pr|mt|mb|mx|my|gap|space-x|space-y)-\d+|(sm|md|lg|xl|2xl):[a-z-]+|text-(xs|sm|base|lg|xl|\dxl)|(bg|text|border)-[a-z]+-\d{2,3}|rounded-(sm|md|lg|xl|full))\b', r'--tw-ring-offset-shadow|--tw-translate-x|tailwindcss|\.sr-only\{position:absolute;width:1px', "high"),
    ("css", "Bootstrap", r'class="[^"]*\b(col-(sm|md|lg|xl|xxl)-\d+|navbar-expand-(sm|md|lg|xl)|container-fluid|row g-\d)\b', r'--bs-blue|--bs-body-bg|bootstrap(\.min)?\.(css|js)|data-bs-toggle', "high"),
    ("css", "styled-components (CSS-in-JS)", r'data-styled(-version)?=|class="[^"]*\bsc-[a-zA-Z0-9]{4,}', r'styled-components|__styled|data-styled', "high"),
    ("css", "Emotion (CSS-in-JS)", r'data-emotion=|class="[^"]*\bcss-[a-z0-9]{5,}', r'@emotion|data-emotion', "high"),
    ("css", "CSS Modules", r'class="[^"]*\b[A-Za-z]+_[A-Za-z0-9]+__[A-Za-z0-9_-]{5,}', r'', "medium"),
    ("css", "Sass / SCSS (source maps)", r'', r'sourceMappingURL=.*\.scss|\.scss', "low"),
    ("css", "vanilla-extract", r'', r'vanilla-extract', "medium"),
    ("css", "Stitches / Panda / StyleX (atomic CSS-in-JS)", r'', r'@stitches|pandacss|stylex', "medium"),
    ("css", "UnoCSS", r'', r'__uno\.css|unocss', "medium"),
    ("css", "Container queries (@container)", r'', r'@container[\s({]|container-type:\s*(inline-size|size)|container:\s*\w+\s*/\s*(inline-size|size)', "high"),
    ("css", "oklch / wide-gamut colour", r'', r'oklch\(|oklab\(|color\(display-p3', "high"),
    ("css", "Cascade layers (@layer)", r'', r'@layer [a-z]', "medium"),
    ("css", "CSS :has() / nesting / @scope", r'', r':has\(|@scope[\s({]|&\s*[.:#>]', "low"),
    ("api", "View Transitions API", r'::view-transition', r'startViewTransition|view-transition-name|::view-transition', "high"),
    ("api", "Popover API", r'\spopover(=|\s|>)|popovertarget=', r'\[popover\]|\.showPopover\(|togglePopover', "high"),
    ("api", "Scroll-driven animations", r'', r'animation-timeline:|scroll\(\)|view\(\)|@scroll-timeline', "medium"),
    ("web-components", "Lit", r'', r'lit-element|lit-html|LitElement|from ?["\x27]lit["\x27]|/@lit/', "high"),
    ("web-components", "Stencil", r'data-stencil|<stencil-', r'@stencil/core|stencil\.js', "high"),
    ("web-components", "Shoelace / Web Awesome", r'<sl-[a-z]|class="[^"]*\bsl-', r'shoelace|@shoelace-style', "high"),
    ("web-components", "Adobe Spectrum Web Components", r'<sp-[a-z]', r'@spectrum-web-components', "high"),
    ("web-components", "Material Web (MWC)", r'<md-[a-z]|<mwc-[a-z]', r'@material/web|material-components', "high"),
    ("web-components", "FAST / Fluent UI", r'<fast-[a-z]|<fluent-[a-z]', r'@microsoft/fast|@fluentui/web-components', "high"),
    ("web-components", "Custom elements (generic)", r'customElements\.define|<[a-z]+-[a-z][a-z-]*[ />]', r'customElements\.define|\.attachShadow\(', "low"),
    ("framework", "Svelte 5 (runes)", r'', r'\$state\(|\$derived\(|\$props\(|\$effect\(|svelte/internal/client', "medium"),
    ("css", "Bulma", r'class="[^"]*\b(columns|column is-|hero is-|navbar-burger)\b', r'bulma', "medium"),
    ("css", "Foundation", r'class="[^"]*\b(grid-x|cell small-|top-bar)\b', r'foundation-sites', "medium"),
    ("ui-library", "Material UI (MUI)", r'class="[^"]*\bMui[A-Z][A-Za-z]+-root', r'@mui/|MuiButtonBase', "high"),
    ("ui-library", "Chakra UI", r'class="[^"]*\bchakra-', r'@chakra-ui', "high"),
    ("ui-library", "Ant Design", r'class="[^"]*\bant-(btn|layout|menu|input)', r'antd|ant-design', "high"),
    ("ui-library", "Radix UI", r'data-radix-|data-state="(open|closed|checked)"[^>]*data-orientation', r'@radix-ui|radix-', "high"),
    ("ui-library", "shadcn/ui", r'data-slot="|cmdk-root', r'cmdk|data-slot', "medium"),
    ("ui-library", "Headless UI", r'id="headlessui-', r'@headlessui', "high"),
    ("ui-library", "Mantine", r'class="[^"]*\bmantine-', r'@mantine', "high"),
    ("ui-library", "Vuetify", r'class="[^"]*\bv-(btn|app|card|navigation-drawer)\b', r'vuetify', "high"),
    ("ui-library", "Element Plus", r'class="[^"]*\bel-(button|input|menu)', r'element-plus', "high"),
    ("ui-library", "PrimeReact / PrimeVue", r'class="[^"]*\bp-(button|inputtext|datatable)\b', r'primereact|primevue', "high"),
    ("ui-library", "DaisyUI", r'class="[^"]*\b(drawer-side|navbar-start|menu-horizontal|join-item)\b', r'daisyui|tailwindcss/plugin.*daisy', "high"),
    ("ui-library", "Flowbite", r'', r'flowbite', "medium"),
    ("icons", "Font Awesome", r'class="[^"]*\bfa[srlb]? fa-|fontawesome', r'fontawesome|fa-solid', "high"),
    ("icons", "Material Icons / Symbols", r'material-icons|material-symbols', r'material-icons', "high"),
    ("icons", "Lucide", r'class="[^"]*\blucide\b|lucide-', r'lucide', "high"),
    ("icons", "Heroicons", r'', r'heroicons', "medium"),
    ("icons", "Iconify", r'class="[^"]*\biconify\b|data-icon=', r'iconify', "high"),
    ("motion", "Framer Motion", r'data-framer-name|data-framer-component', r'framer-motion|motion\.div|useAnimation|AnimatePresence', "medium"),
    ("motion", "GSAP", r'', r'gsap|TweenMax|ScrollTrigger', "high"),
    ("motion", "Lottie", r'<lottie-player|data-lottie', r'lottie-web|lottie\.loadAnimation|bodymovin', "high"),
    ("motion", "Three.js / WebGL", r'', r'three(\.min)?\.js|THREE\.WebGLRenderer|@react-three/fiber', "high"),
    ("motion", "Lenis / smooth scroll", r'class="[^"]*\blenis\b', r'lenis|locomotive-scroll', "high"),
    ("motion", "AOS (Animate On Scroll)", r'data-aos=', r'aos\.js|AOS\.init', "high"),
    ("motion", "Swiper", r'class="[^"]*\bswiper(-wrapper|-slide)?\b', r'swiper', "high"),
    ("builder", "Webflow", r'data-wf-site|data-wf-page|class="w-(nav|container|button|embed)', r'webflow\.js|Webflow\.require', "high"),
    ("builder", "WordPress", r'wp-content/|wp-includes/|<meta name="generator" content="WordPress', r'wp-content', "high"),
    ("builder", "Elementor", r'elementor-', r'elementor', "high"),
    ("builder", "Shopify", r'cdn\.shopify\.com|Shopify\.theme|shopify-section', r'Shopify\.', "high"),
    ("builder", "Squarespace", r'content="Squarespace|static1\.squarespace\.com', r'squarespace', "high"),
    ("builder", "Wix", r'content="Wix\.com|static\.wixstatic\.com|parastorage', r'wixstatic', "high"),
    ("builder", "Framer (site builder)", r'content="Framer|framerusercontent\.com', r'framerusercontent', "high"),
    ("builder", "Webflow / Carrd / Notion-like (generic)", r'content="Carrd', r'', "medium"),
    ("builder", "HubSpot CMS", r'hs-sites|hubspot', r'hubspot', "medium"),
    ("builder", "Ghost (CMS)", r'content="Ghost\b|/ghost/api/|data-ghost', r'@tryghost|ghost-sdk|/ghost/api/', "high"),
    ("bundler", "webpack", r'', r'webpackChunk|__webpack_require__|webpackJsonp', "high"),
    ("bundler", "Vite / Rollup", r'', r'__vitePreload|modulepreload|\bimport\.meta\b', "low"),
    ("bundler", "Parcel", r'', r'parcelRequire', "high"),
    ("bundler", "esbuild", r'', r'__esbuild|var __defProp = Object\.defineProperty', "low"),
    ("bundler", "Turbopack", r'', r'__turbopack', "high"),
    ("analytics", "Google Analytics / GTM", r'googletagmanager\.com|google-analytics\.com|gtag\(', r'gtag\(|dataLayer', "high"),
    ("analytics", "Segment", r'cdn\.segment\.com', r'analytics\.load', "high"),
    ("analytics", "Hotjar", r'static\.hotjar\.com', r'hotjar', "high"),
    ("analytics", "Plausible", r'plausible\.io', r'plausible', "high"),
    ("analytics", "PostHog", r'posthog', r'posthog', "high"),
    ("analytics", "Mixpanel", r'mixpanel', r'mixpanel', "high"),
    ("analytics", "Sentry", r'sentry', r'Sentry\.init|@sentry', "high"),
    ("analytics", "Intercom / Crisp / Drift (chat widget)", r'intercom|crisp\.chat|drift\.com', r'Intercom\(|\$crisp', "medium"),
    ("fonts", "Google Fonts", r'fonts\.googleapis\.com|fonts\.gstatic\.com', r'fonts\.googleapis', "high"),
    ("fonts", "Adobe Fonts (Typekit)", r'use\.typekit\.net', r'typekit', "high"),
    ("fonts", "Fontshare / Bunny / Fontsource (self-host)", r'fontshare\.com|fonts\.bunny\.net|fontsource', r'', "medium"),
    ("fonts", "Self-hosted @font-face", r'', r'@font-face', "low"),
    ("images", "Next/Image or image CDN", r'/_next/image\?|imgix\.net|cloudinary\.com|images\.ctfassets|res\.cloudinary', r'', "medium"),
    ("hosting", "Vercel", r'vercel', r'vercel', "low"),
    ("hosting", "Netlify", r'netlify', r'netlify', "low"),
    ("hosting", "Cloudflare", r'cloudflare|cdn-cgi/', r'', "low"),
]

def fetch(url, binary=False, limit=6_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read(limit)
        ctype = r.headers.get("content-type", "")
    return data if binary else data.decode("utf-8", "replace"), ctype

def load_target(target, max_scripts):
    """Returns (html, assets[list of (url, text)], source_description)."""
    if os.path.isdir(target):
        cap = None
        for root, _, files in os.walk(target):
            if "capture.json" in files: cap = os.path.join(root, "capture.json"); break
        if not cap: sys.exit("no capture.json found under " + target)
        d = os.path.dirname(cap)
        html = open(os.path.join(d, "dom.html"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(d, "dom.html")) else ""
        assets = []
        sd = os.path.join(d, "styles")
        if os.path.isdir(sd):
            for f in sorted(os.listdir(sd)): assets.append((f, open(os.path.join(sd, f), encoding="utf-8", errors="replace").read()))
        capj = json.load(open(cap, encoding="utf-8"))
        base = capj.get("url", "")
        n = 0
        for s in capj.get("scripts", []):
            if s.get("src") and n < max_scripts and s["src"].startswith("http"):
                try: assets.append((s["src"], fetch(s["src"])[0])); n += 1
                except Exception as e: assets.append((s["src"], ""))
        return html, assets, "capture dir " + d, capj
    if os.path.isfile(target):
        html = open(target, encoding="utf-8", errors="replace").read()
        return html, [], "file " + target, None
    url = target if re.match(r'^https?://', target) else "https://" + target
    try: html, _ = fetch(url)
    except Exception as e:
        sys.exit(f"could not download {url}: {e}\nIf the network is restricted, capture the page with capture_page.js (or save it from a browser) and pass that directory/file instead.")
    assets = []
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)', html) + re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)', html) + re.findall(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet', html)
    seen = set()
    for s in srcs:
        u = urllib.parse.urljoin(url, htmlmod.unescape(s))
        if u in seen or len(seen) >= max_scripts: continue
        seen.add(u)
        try: assets.append((u, fetch(u)[0]))
        except Exception: assets.append((u, ""))
    return html, assets, "url " + url, None

def detect(html, assets, capj=None):
    findings = []
    asset_text = "\n".join(t for _, t in assets)
    for cat, name, html_re, asset_re, conf in SIGNATURES:
        ev = []
        if html_re:
            m = re.search(html_re, html, re.I)
            if m: ev.append("html: " + html[max(0, m.start()-30):m.end()+30].replace("\n", " ")[:120])
        if asset_re:
            for u, t in assets:
                m = re.search(asset_re, t, re.I)
                if m: ev.append(f"{os.path.basename(u)[:50]}: " + t[max(0, m.start()-25):m.end()+25].replace("\n", " ")[:110]); break
        if ev:
            findings.append({"category": cat, "name": name, "confidence": conf if len(ev) > 1 or conf == "high" else ("medium" if conf == "high" else conf), "evidence": ev})
    if capj:
        for k, v in (capj.get("frameworkHints") or {}).items():
            if v: findings.append({"category": "runtime-hint", "name": k, "confidence": "medium", "evidence": ["capture_page.js runtime global/DOM probe"]})
        sh = capj.get("shadow") or {}
        if sh.get("hosts"): findings.append({"category": "web-components", "name": f"Shadow DOM in use ({sh['hosts']} host(s), {sh.get('nodes',0)} shadow node(s))", "confidence": "high", "evidence": ["capture pierced open shadow roots at runtime"]})
        ce = capj.get("customElements") or []
        if ce: findings.append({"category": "web-components", "name": "Custom elements: " + ", ".join(ce[:8]), "confidence": "high", "evidence": ["custom element tags observed in the DOM"]})
        if capj.get("containerQueries"): findings.append({"category": "css", "name": f"Container queries ({len(capj['containerQueries'])} distinct)", "confidence": "high", "evidence": [list(capj['containerQueries'].keys())[0][:70]]})
        if capj.get("generator"): findings.append({"category": "builder", "name": "meta generator: " + capj["generator"], "confidence": "high", "evidence": ["<meta name=generator>"]})
    gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if gen and not capj: findings.append({"category": "builder", "name": "meta generator: " + gen.group(1), "confidence": "high", "evidence": ["<meta name=generator>"]})
    # Rendering mode heuristics
    body_text = re.sub(r'<script.*?</script>|<style.*?</style>', '', html, flags=re.S | re.I)
    visible = len(re.sub(r'<[^>]+>', '', body_text).strip())
    mode = "client-rendered shell (little HTML content before JS runs)" if visible < 400 and re.search(r'<div id="(root|app|__next|__nuxt)"', html) else "server-rendered or static HTML (content present before JS)"
    smaps = len(re.findall(r'sourceMappingURL=', asset_text))
    return {
        "findings": sorted(findings, key=lambda f: (f["category"], f["name"])),
        "renderingMode": mode, "visibleTextBytes": visible,
        "sourceMapsReferenced": smaps,
        "assetsInspected": [{"url": u[:200], "bytes": len(t)} for u, t in assets],
        "notes": ["Signatures are heuristics on shipped text; a match proves presence of a marker, not that the library drives the UI you care about.",
                  "Absence of a match is not evidence of absence: minified bundles can strip every readable marker."]
    }

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    target = argv[0]; as_json = "--json" in argv; max_scripts = 12
    if "--max-scripts" in argv: max_scripts = int(argv[argv.index("--max-scripts") + 1])
    html, assets, src, capj = load_target(target, max_scripts)
    res = detect(html, assets, capj); res["source"] = src
    if as_json: print(json.dumps(res, indent=1)); return 0
    print(f"Source: {src}\nRendering: {res['renderingMode']}  (visible text bytes: {res['visibleTextBytes']}, source maps: {res['sourceMapsReferenced']})\n")
    cur = None
    for f in res["findings"]:
        if f["category"] != cur: cur = f["category"]; print(f"[{cur}]")
        print(f"  {f['name']:<48} {f['confidence']:<7} {f['evidence'][0][:90]}")
    print("\n" + "\n".join("note: " + n for n in res["notes"]))
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

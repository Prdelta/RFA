#!/usr/bin/env python3
"""whitelabel.py - turn an extracted design into a brand-neutral, themeable
template (a "marca blanca" / white-label starter) where every brand decision
lives in one config and a single swap re-skins the whole thing.

Usage:
    python3 whitelabel.py --tokens tokens.json [--capture dir|capture.json ...]
        [--brand-name "Acme"] [--stack tailwind|css] [--out dir] [--json]

The idea: a faithful replica hardcodes the original's blue, its font and its
logo everywhere. A white-label template does the opposite. It keeps what is
generic and reusable (the layout skeleton, the spacing/radius/shadow scale,
the type scale, the breakpoints, the component structure) and lifts everything
brand-specific (hues, fonts, logo, name, imagery, marketing copy) into a
`brand.config` of named variables. The template ships with a NEUTRAL default
theme; the original's values are kept only as one example theme for reference
and parity, never as the default you distribute.

Outputs into --out (default: next to tokens.json):
  whitelabel.json        machine summary: role map, theming contract, assets
  brand.config.json      single source of brand truth (neutral default + captured example)
  theme.neutral.css      :root variables with the brand-neutral default — SHIP THIS
  theme.captured.css     the original's values behind the same variables (reference/parity only)
  tailwind.theme.js      theme.extend wired to the variables (with --stack tailwind)
  brand-assets.md        checklist of brand-bound assets to replace (logo, name, fonts, images, copy)

Separates what is a reusable structural token from what is a brand decision, so
the resulting template is generic and the original's protected assets (logo,
name, verbatim copy, proprietary fonts, photos) are flagged for replacement
rather than carried over. Standard library only.
"""
import json, os, re, sys
from urllib.parse import urlparse

# A documented brand-neutral default palette (indigo primary, slate neutrals).
# This is the "unbranded" skin the template ships with; swap for a real brand later.
NEUTRAL = {
    "primary": "#4f46e5", "primary-hover": "#4338ca", "primary-contrast": "#ffffff",
    "secondary": "#0ea5e9", "accent": "#f59e0b",
    "bg": "#ffffff", "surface": "#f8fafc", "text": "#0f172a", "text-muted": "#64748b",
    "border": "#e2e8f0",
    "bg-dark": "#0b1120", "surface-dark": "#111827", "text-dark": "#e2e8f0", "border-dark": "#1e293b",
}
OPEN_FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "fontsource", "fonts.bunny.net", "api.fontshare.com", "cdn.fontshare.com")
FONT_SUBS = [
    (r"helvetica|arial|aktiv|neue haas|roboto|-apple-system|system-ui|segoe|sf pro|inter", "Inter", "sans"),
    (r"georgia|times|garamond|serif|tiempos|freight|source serif|lora|merriweather", "Source Serif 4", "serif"),
    (r"mono|consolas|menlo|courier|jetbrains|fira code|ibm plex mono", "JetBrains Mono", "mono"),
    (r"poppins|montserrat|circular|gilroy|futura|sofia|geist", "Plus Jakarta Sans", "sans"),
]

def rd(p):
    return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else None

def load_caps(paths):
    caps = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                if "capture.json" in files: caps.append(rd(os.path.join(root, "capture.json")))
        elif os.path.isfile(p): caps.append(rd(p))
    return [c for c in caps if c]

def font_substitute(family):
    f = (family or "").lower()
    for pat, sub, kind in FONT_SUBS:
        if re.search(pat, f): return sub, kind
    return "Inter", "sans"   # unknown/proprietary → neutral open default

def _rgb(h): h = h.lstrip("#"); return tuple(int(h[k:k+2], 16) for k in (0, 2, 4))
def _chroma(h):
    r, g, b = _rgb(h); return max(r, g, b) - min(r, g, b)
def _lum(h):
    r, g, b = [c / 255 for c in _rgb(h)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
def _hue(h):
    r, g, b = [c / 255 for c in _rgb(h)]; mx, mn = max(r, g, b), min(r, g, b); d = mx - mn
    if d == 0: return 0
    if mx == r: hh = ((g - b) / d) % 6
    elif mx == g: hh = (b - r) / d + 2
    else: hh = (r - g) / d + 4
    return hh * 60
def _darken(h, f=0.82):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * f))) for c in _rgb(h))
def _hue_delta(a, b):
    d = abs(_hue(a) - _hue(b)); return min(d, 360 - d)

def classify_colors(tokens):
    """Map the captured palette to semantic brand roles. Brand colours are the
    SATURATED ones (high chroma), not merely the most frequent — a muted slate
    grey used on every paragraph is text, not the brand. Neutrals (greys) fill
    background, surface, muted text and border by luminance."""
    opaque = []
    for bucket in ("accent", "neutral"):
        for c in tokens["colors"][bucket]:
            if len(c["hex"]) == 7:  # drop translucent tints like #0d94881f
                opaque.append({"hex": c["hex"], "uses": c["uses"], "roles": c.get("roles", {}), "chroma": _chroma(c["hex"]), "lum": _lum(c["hex"])})
    # gradient stops carry brand hues (e.g. a teal->sky hero) that may be used
    # too rarely to rank as flat colours; mine them as secondary/accent candidates.
    grad_hues = []
    for g in tokens.get("gradients", []):
        for m in re.findall(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", g.get("value", "")):
            h = "#%02x%02x%02x" % tuple(int(x) for x in m)
            if _chroma(h) >= 60: grad_hues.append({"hex": h, "uses": 1, "roles": {}, "chroma": _chroma(h), "lum": _lum(h)})
    brandy = sorted([c for c in opaque if c["chroma"] >= 60], key=lambda c: (-c["chroma"], -c["uses"]))
    grey = sorted([c for c in opaque if c["chroma"] < 60], key=lambda c: c["lum"])
    accent_sorted = sorted(opaque, key=lambda c: -c["uses"])
    roles = {}
    if brandy:
        primary = brandy[0]["hex"]
        same_hue_darker = [c for c in brandy if c["hex"] != primary and _hue_delta(c["hex"], primary) < 30 and c["lum"] < brandy[0]["lum"]]
        roles["primary"] = primary
        roles["primary-hover"] = min(same_hue_darker, key=lambda c: c["lum"])["hex"] if same_hue_darker else _darken(primary)
        pool = brandy + [g for g in grad_hues if g["hex"] != primary]
        seen_h = set()
        other_hue = []
        for c in sorted(pool, key=lambda c: -c["chroma"]):
            if _hue_delta(c["hex"], primary) >= 20 and c["hex"] not in seen_h:
                seen_h.add(c["hex"]); other_hue.append(c)
        roles["secondary"] = other_hue[0]["hex"] if other_hue else roles["primary-hover"]
        roles["accent"] = other_hue[1]["hex"] if len(other_hue) > 1 else (other_hue[0]["hex"] if other_hue else roles["secondary"])
    else:
        primary = (accent_sorted[0]["hex"] if accent_sorted else "#2563eb")
        roles["primary"] = primary; roles["primary-hover"] = _darken(primary); roles["secondary"] = primary; roles["accent"] = primary
    bg = tokens["page"]["background"]; text = tokens["page"]["text"]
    roles["bg"] = bg; roles["text"] = text
    lbg = _lum(bg) if len(bg) == 7 else 1.0; ltext = _lum(text) if len(text) == 7 else 0.0
    # surface: a near-bg grey, slightly off the page background
    surf = [c for c in grey if c["hex"] != bg and abs(c["lum"] - lbg) < 0.12]
    roles["surface"] = (min(surf, key=lambda c: abs(c["lum"] - lbg))["hex"] if surf else bg)
    # border: light grey clearly separated from bg but still pale
    bord = [c for c in grey if c["hex"] not in (bg, roles["surface"]) and 0.55 < c["lum"] < lbg + 0.001]
    roles["border"] = (max(bord, key=lambda c: c["uses"])["hex"] if bord else (grey[-1]["hex"] if grey else "#e5e7eb"))
    # muted text: a mid grey between text and background, most used
    mid = [c for c in grey if ltext + 0.02 < c["lum"] < 0.55 and c["hex"] not in (roles["border"], text)]
    roles["text-muted"] = (max(mid, key=lambda c: c["uses"])["hex"] if mid else next((c["hex"] for c in grey if c["hex"] not in (bg, roles["border"], text)), "#6b7280"))
    accent = tokens["colors"]["accent"]; neutral = tokens["colors"]["neutral"]
    ramp = [c["hex"] for c in neutral if c["hex"] not in (bg, text)]
    return roles, accent, neutral, ramp

def find_brand_assets(caps, brand_name, tokens):
    logos, favicons, images, copy, names = [], [], [], [], set()
    for cap in caps:
        if cap.get("title"): names.add(re.split(r"[|–—\-·:]", cap["title"])[0].strip())
        for l in cap.get("links", []):
            if l.get("rel") and "icon" in l["rel"]: favicons.append(l["href"])
        by_id = {n["id"]: n for n in cap.get("nodes", [])}
        def in_header(n):
            cur, d = n, 0
            while cur is not None and d < 8:
                if cur["tag"] in ("header", "nav") or cur["attrs"].get("role") in ("banner", "navigation"): return True
                cur = by_id.get(cur["parent"]) if cur["parent"] is not None else None; d += 1
            return False
        for n in cap.get("nodes", []):
            a = n["attrs"]
            if n["tag"] == "img" and a.get("src"):
                (logos if in_header(n) else images).append({"src": a["src"], "alt": a.get("alt", ""), "box": [n["rect"]["w"], n["rect"]["h"]]})
            if n["tag"] == "svg" and in_header(n): logos.append({"src": "inline <svg>", "box": [n["rect"]["w"], n["rect"]["h"]]})
            if n["tag"] in ("h1", "h2") and n["text"]: copy.append({"tag": n["tag"], "text": n["text"]})
            if n["tag"] == "p" and n["text"] and len(n["text"]) > 30 and len(copy) < 12: copy.append({"tag": "p", "text": n["text"]})
    if brand_name: names = {brand_name}
    src = (tokens.get("source") or [None])[0]
    if src:
        host = urlparse(src).netloc.replace("www.", "")
        if host: names.add(host.split(".")[0].capitalize())
    # fonts to replace
    font_flags = []
    seen = set()
    for ff in tokens["typography"].get("fontFaces", []):
        fam = (ff.get("family") or "").strip().strip('"\'')
        if not fam or fam.lower() in seen: continue
        seen.add(fam.lower())
        src_url = ff.get("src", "")
        host = ""
        m = re.search(r"url\((['\"]?)(https?://[^)'\"]+)", src_url)
        if m: host = urlparse(m.group(2)).netloc
        is_open = any(h in src_url or h in host for h in OPEN_FONT_HOSTS)
        sub, kind = font_substitute(fam)
        font_flags.append({"family": fam, "selfHostedOrPaid": not is_open and bool(src_url), "host": host, "openSubstitute": sub, "role": kind})
    # also families from usage with no @font-face (system/webfont)
    for f in tokens["typography"]["families"][:3]:
        fam = f["value"]
        if fam.lower() in seen or fam.lower() in ("", "inherit"): continue
        seen.add(fam.lower()); sub, kind = font_substitute(fam)
        font_flags.append({"family": fam, "selfHostedOrPaid": False, "host": "", "openSubstitute": sub, "role": kind})
    return {"logos": logos[:8], "favicons": list(dict.fromkeys(favicons))[:6], "images": images[:12], "brandNameCandidates": sorted(n for n in names if n), "marketingCopy": copy[:12], "fonts": font_flags}

def build(tokens, caps, brand_name, stack):
    roles, accent, neutral, ramp = classify_colors(tokens)
    assets = find_brand_assets(caps, brand_name, tokens)
    display_font = next((f for f in assets["fonts"] if f["role"] in ("serif", "sans")), None)
    body_font = assets["fonts"][0] if assets["fonts"] else {"family": "Inter", "openSubstitute": "Inter", "role": "sans"}
    # generic scale carried over as the template base (not brand)
    radius = [r["value"] for r in tokens["radii"][:4]]
    spacing_base = tokens["spacing"]["baseUnitGuess"]
    shadows = [s["value"] for s in tokens["shadows"][:4]]
    bps = [{"name": f"bp{b['px']}", "px": b["px"]} for b in tokens["layout"]["breakpoints"] if b["kind"] == "min-width"][:6]
    # The theming contract: the minimal variables to flip to re-skin.
    contract = ["--brand-primary", "--brand-primary-hover", "--brand-secondary", "--brand-accent",
                "--brand-font-display", "--brand-font-body", "--brand-radius", "--brand-logo", "--brand-name"]
    captured = {k: roles[k] for k in ("primary", "primary-hover", "secondary", "accent", "bg", "surface", "text", "text-muted", "border")}
    captured["primary-contrast"] = "#ffffff"
    config = {
        "$comment": "Single source of brand truth. Ship with theme 'neutral'; 'captured-example' holds the original's values for reference and parity only. Flip the theming contract variables to re-brand.",
        "brand": {"name": (assets["brandNameCandidates"][0] if assets["brandNameCandidates"] else "{{BRAND_NAME}}"),
                   "logo": "assets/logo.svg", "favicon": "assets/favicon.svg",
                   "fonts": {"display": (display_font or body_font)["openSubstitute"], "body": body_font["openSubstitute"], "mono": "JetBrains Mono"}},
        "themes": {"neutral": NEUTRAL, "captured-example": captured},
        "scale": {"radius": radius, "spacingBasePx": spacing_base, "shadows": shadows,
                   "breakpoints": bps, "containerMaxWidth": (tokens["layout"]["containerMaxWidths"][0]["value"] if tokens["layout"]["containerMaxWidths"] else None),
                   "typeScale": [{"step": s["tag"], "size": s["size"], "weight": s["weight"], "lineHeight": s["lineHeight"]} for s in tokens["typography"]["scale"][:8]],
                   "motion": {"durations": [d["value"] for d in tokens["motion"]["durations"][:4]], "easings": [e["value"] for e in tokens["motion"]["easings"][:3]]}},
        "themingContract": contract,
    }
    return config, assets, (display_font or body_font), body_font

def theme_css(theme, brand, scale, which):
    L = [f"/* {which} theme — edit these to re-brand the whole template */", ":root {"]
    L.append(f'  --brand-name: "{brand["name"]}";')
    L.append(f'  --brand-font-display: "{brand["fonts"]["display"]}", system-ui, sans-serif;')
    L.append(f'  --brand-font-body: "{brand["fonts"]["body"]}", system-ui, sans-serif;')
    L.append(f'  --brand-font-mono: "{brand["fonts"]["mono"]}", ui-monospace, monospace;')
    for k, v in theme.items():
        if k.endswith("-dark"): continue
        L.append(f"  --brand-{k}: {v};")
    if scale["radius"]: L.append(f"  --brand-radius: {scale['radius'][0]};")
    for i, r in enumerate(scale["radius"]): L.append(f"  --radius-{i+1}: {r};")
    if scale["spacingBasePx"]: L.append(f"  --space-unit: {scale['spacingBasePx']}px;")
    for i, s in enumerate(scale["shadows"]): L.append(f"  --shadow-{i+1}: {s};")
    L.append("}")
    dark = {k[:-5]: v for k, v in theme.items() if k.endswith("-dark")}
    if dark:
        L.append("\n@media (prefers-color-scheme: dark) {\n  :root:not([data-theme=\"light\"]) {")
        for k, v in dark.items(): L.append(f"    --brand-{k}: {v};")
        L.append("  }\n}")
    return "\n".join(L) + "\n"

def assets_md(assets, fonts):
    L = ["# Brand assets to replace\n", "These are the brand-bound parts of the original. A white-label template must",
         "not ship them; replace each with your own or a neutral placeholder.\n"]
    L.append("## Brand name\nOriginal candidates: " + (", ".join(assets["brandNameCandidates"]) or "none detected") + "\nReplace every occurrence with `{{BRAND_NAME}}` wired to `--brand-name`.\n")
    L.append("## Logo and favicon")
    for lg in assets["logos"]: L.append(f"- logo: {lg['src']} (box {lg.get('box')})")
    for fv in assets["favicons"]: L.append(f"- favicon: {fv}")
    if not assets["logos"] and not assets["favicons"]: L.append("- none detected in header/nav; check manually")
    L.append("Replace with a placeholder mark wired to `--brand-logo`.\n")
    L.append("## Fonts")
    for f in fonts:
        flag = "SELF-HOSTED/PAID — verify licence, do not redistribute" if f["selfHostedOrPaid"] else "check licence"
        L.append(f"- {f['family']} ({flag}) → open substitute **{f['openSubstitute']}**")
    L.append("Ship the template with the open substitutes; wire via `--brand-font-*`.\n")
    L.append("## Imagery (not reusable — replace with placeholders of the same aspect ratio)")
    for im in assets["images"][:10]: L.append(f"- {im['src']}  alt={im.get('alt','')!r}  box={im.get('box')}")
    if not assets["images"]: L.append("- none detected")
    L.append("\n## Marketing copy (rewrite — do not ship verbatim)")
    for c in assets["marketingCopy"][:10]: L.append(f"- <{c['tag']}> {c['text'][:80]!r}")
    return "\n".join(L) + "\n"

def tailwind_js(config):
    t = config["themes"]["neutral"]; s = config["scale"]
    theme = {"colors": {"brand": {"DEFAULT": "var(--brand-primary)", "hover": "var(--brand-primary-hover)", "secondary": "var(--brand-secondary)", "accent": "var(--brand-accent)"},
                         "bg": "var(--brand-bg)", "surface": "var(--brand-surface)", "ink": "var(--brand-text)", "muted": "var(--brand-text-muted)", "line": "var(--brand-border)"},
             "fontFamily": {"display": ["var(--brand-font-display)"], "sans": ["var(--brand-font-body)"], "mono": ["var(--brand-font-mono)"]},
             "borderRadius": {f"r{i+1}": r for i, r in enumerate(s["radius"])},
             "screens": {b["name"]: f"{b['px']}px" for b in s["breakpoints"]}}
    return "// tailwind.config.js -> theme.extend. Colours read CSS vars, so theme.neutral.css / brand.config drive the brand.\nmodule.exports = " + json.dumps(theme, indent=2) + ";\n"

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    opts = {"capture": []}; i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        if k == "capture": opts["capture"].append(argv[i+1]); i += 2
        elif k == "json": opts["json"] = True; i += 1
        else: opts[k] = argv[i+1]; i += 2
    tokens = rd(opts.get("tokens"))
    if not tokens: sys.exit("need --tokens tokens.json (from extract_tokens.py)")
    caps = load_caps(opts["capture"])
    out = opts.get("out") or os.path.dirname(os.path.abspath(opts["tokens"]))
    os.makedirs(out, exist_ok=True)
    config, assets, display_font, body_font = build(tokens, caps, opts.get("brand-name"), opts.get("stack", "css"))
    json.dump(config, open(os.path.join(out, "brand.config.json"), "w", encoding="utf-8"), indent=1)
    neutral_brand = {**config["brand"], "name": "Your Brand"}  # ship a placeholder name, not the original's
    open(os.path.join(out, "theme.neutral.css"), "w", encoding="utf-8").write(theme_css(config["themes"]["neutral"], neutral_brand, config["scale"], "NEUTRAL (ship this)"))
    cap_brand = dict(config["brand"]); cap_brand = {**config["brand"], "fonts": {"display": display_font["family"], "body": body_font["family"], "mono": "JetBrains Mono"}}
    open(os.path.join(out, "theme.captured.css"), "w", encoding="utf-8").write(theme_css(config["themes"]["captured-example"], cap_brand, config["scale"], "CAPTURED original (reference/parity only)"))
    open(os.path.join(out, "brand-assets.md"), "w", encoding="utf-8").write(assets_md(assets, assets["fonts"]))
    if opts.get("stack") == "tailwind": open(os.path.join(out, "tailwind.theme.js"), "w", encoding="utf-8").write(tailwind_js(config))
    summary = {"themingContract": config["themingContract"], "brandName": config["brand"]["name"], "fonts": assets["fonts"],
               "roles": {k: config["themes"]["captured-example"][k] for k in ("primary", "secondary", "accent", "bg", "text")},
               "assetsToReplace": {"logos": len(assets["logos"]), "favicons": len(assets["favicons"]), "images": len(assets["images"]), "copyBlocks": len(assets["marketingCopy"])},
               "genericScaleCarriedOver": {"radius": config["scale"]["radius"], "spacingBasePx": config["scale"]["spacingBasePx"], "breakpoints": [b["px"] for b in config["scale"]["breakpoints"]]}}
    json.dump(summary, open(os.path.join(out, "whitelabel.json"), "w", encoding="utf-8"), indent=1)
    if opts.get("json"): print(json.dumps(summary, indent=1)); return 0
    print(f"Brand name candidates: {', '.join(assets['brandNameCandidates']) or '(none)'}")
    print(f"Brand colours (captured → neutralised): primary {config['themes']['captured-example']['primary']} → {NEUTRAL['primary']}")
    print("Theming contract (flip these to re-skin):")
    for v in config["themingContract"]: print("  " + v)
    print("Fonts to replace:")
    for f in assets["fonts"]: print(f"  {f['family']}{' [self-hosted/paid]' if f['selfHostedOrPaid'] else ''} → {f['openSubstitute']}")
    print(f"Assets to replace: {len(assets['logos'])} logo(s), {len(assets['favicons'])} favicon(s), {len(assets['images'])} image(s), {len(assets['marketingCopy'])} copy block(s)")
    print(f"Generic scale carried into the template: radius {config['scale']['radius']}, spacing base {config['scale']['spacingBasePx']}px, breakpoints {[b['px'] for b in config['scale']['breakpoints']]}")
    print(f"\nWrote brand.config.json, theme.neutral.css, theme.captured.css, brand-assets.md{', tailwind.theme.js' if opts.get('stack') == 'tailwind' else ''}, whitelabel.json to {out}")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

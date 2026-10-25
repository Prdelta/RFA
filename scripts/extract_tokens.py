#!/usr/bin/env python3
"""extract_tokens.py - derive design tokens from one or more capture.json files
written by capture_page.js.

Usage:
    python3 extract_tokens.py <capture.json | capture-dir> [more...] [--out <dir>] [--min-uses N] [--json]

Writes into --out (default: next to the first capture):
    tokens.json      palette, typography, spacing, radii, shadows, borders,
                     breakpoints, z-index layers, motion, each with usage counts
                     and, when available, the CSS custom property that carries it
    tokens.css       :root custom properties ready to paste
    tailwind.theme.js  a theme.extend snippet with the same values

Values are ranked by how many visible elements use them. A value used once is
usually a one-off, not a token; --min-uses (default 2) filters those out of the
CSS/Tailwind output but keeps them in tokens.json under "rare".
Standard library only.
"""
import json, os, re, sys, math
from collections import Counter, defaultdict

def load_captures(paths):
    caps = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                if "capture.json" in files: caps.append(json.load(open(os.path.join(root, "capture.json"), encoding="utf-8")))
        elif os.path.isfile(p): caps.append(json.load(open(p, encoding="utf-8")))
    if not caps: sys.exit("no capture.json found")
    return caps

RGB_RE = re.compile(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)')

def split_top(s):
    """Split a CSS list on top-level commas only, so cubic-bezier(a, b, c, d)
    stays intact as one value."""
    out, depth, cur = [], 0, ""
    for ch in s or "":
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0: out.append(cur.strip()); cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out

def _hsl_to_rgb(hh, s, l):
    import math
    hh = (hh % 360) / 360.0
    def f(p, q, tt):
        if tt < 0: tt += 1
        if tt > 1: tt -= 1
        if tt < 1/6: return p + (q - p) * 6 * tt
        if tt < 1/2: return q
        if tt < 2/3: return p + (q - p) * (2/3 - tt) * 6
        return p
    if s == 0: r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s; p = 2 * l - q
        r = f(p, q, hh + 1/3); g = f(p, q, hh); b = f(p, q, hh - 1/3)
    return round(r * 255), round(g * 255), round(b * 255)

def to_hex(v):
    """Computed colours come back as rgb()/rgba(), but authored hsl()/hsla()
    and color(srgb ...)/color(display-p3 ...) can survive to computed in modern
    engines. Parse all of them to #rrggbb[aa]; return None only for truly
    transparent or unparseable values."""
    if not v: return None
    v = v.strip()
    m = RGB_RE.match(v)
    if m:
        r, g, b, a = int(m[1]), int(m[2]), int(m[3]), m[4]
        if a is not None and float(a) == 0: return None
        h = "#%02x%02x%02x" % (r, g, b)
        if a is not None and float(a) < 1: h += "%02x" % round(float(a) * 255)
        return h
    m = re.match(r'hsla?\(\s*([\d.]+)(?:deg)?[,\s]+([\d.]+)%[,\s]+([\d.]+)%(?:\s*[,/]\s*([\d.]+%?))?\s*\)', v)
    if m:
        a = m[4]
        if a is not None:
            av = float(a[:-1]) / 100 if a.endswith('%') else float(a)
            if av == 0: return None
        r, g, b = _hsl_to_rgb(float(m[1]), float(m[2]) / 100, float(m[3]) / 100)
        h = "#%02x%02x%02x" % (r, g, b)
        if a is not None and av < 1: h += "%02x" % round(av * 255)
        return h
    m = re.match(r'color\((?:srgb|display-p3)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+))?\s*\)', v)
    if m:
        a = m[4]
        if a is not None and float(a) == 0: return None
        r, g, b = [max(0, min(255, round(float(x) * 255))) for x in (m[1], m[2], m[3])]
        h = "#%02x%02x%02x" % (r, g, b)
        if a is not None and float(a) < 1: h += "%02x" % round(float(a) * 255)
        return h
    m = re.match(r'okl(ch|ab)\(\s*([\d.]+%?)\s+(-?[\d.]+%?)\s+(-?[\d.]+)(?:deg)?(?:\s*/\s*([\d.]+%?))?\s*\)', v)
    if m:
        kind = m.group(1); a = m.group(5)
        if a is not None:
            av = float(a[:-1]) / 100 if a.endswith('%') else float(a)
            if av == 0: return None
        L = float(m.group(2)[:-1]) / 100 if m.group(2).endswith('%') else float(m.group(2))
        if kind == 'ch':
            C = float(m.group(3)[:-1]) * 0.4 / 100 if m.group(3).endswith('%') else float(m.group(3))
            H = float(m.group(4)); oa = C * math.cos(math.radians(H)); ob = C * math.sin(math.radians(H))
        else:
            oa = float(m.group(3)[:-1]) * 0.4 / 100 if m.group(3).endswith('%') else float(m.group(3)); ob = float(m.group(4))
        l_ = (L + 0.3963377774 * oa + 0.2158037573 * ob) ** 3
        m_ = (L - 0.1055613458 * oa - 0.0638541728 * ob) ** 3
        s_ = (L - 0.0894841775 * oa - 1.2914855480 * ob) ** 3
        rl = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
        gl = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
        bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
        def g2(c):
            c = max(0.0, min(1.0, c)); return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        r, gg, b = [max(0, min(255, round(g2(x) * 255))) for x in (rl, gl, bl)]
        hx = "#%02x%02x%02x" % (r, gg, b)
        if a is not None and av < 1: hx += "%02x" % round(av * 255)
        return hx
    return None

def luminance(hexv):
    r, g, b = [int(hexv[i:i+2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def contrast(a, b):
    la, lb = luminance(a[:7]), luminance(b[:7]); hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)

def px(v):
    m = re.match(r'^(-?[\d.]+)px$', v.strip()); return float(m[1]) if m else None

def extract(caps, min_uses):
    colors = defaultdict(Counter)   # role -> hex -> count
    bg_area = Counter(); body_bg = None; body_text = None
    fonts = Counter(); sizes = Counter(); weights = Counter(); lh = Counter(); ls = Counter(); type_combos = Counter()
    spacing = Counter(); gaps = Counter(); radii = Counter(); shadows = Counter(); borders = Counter(); zidx = Counter()
    durations = Counter(); easings = Counter(); transitions = Counter(); widths = Counter(); gradients = Counter(); lh_ratio = Counter(); low_contrast = {}; gradient_text = False
    prop_by_value = defaultdict(set)
    for cap in caps:
        for name, vals in (cap.get("customProperties") or {}).items():
            for v in vals:
                hx = to_hex(v["value"]) or v["value"].strip().lower()
                prop_by_value[hx].add(name)
        for name, v in (cap.get("customPropertiesRoot") or {}).items():
            prop_by_value[to_hex(v) or v.strip().lower()].add(name)
        for n in cap.get("nodes", []):
            s = n["styles"]; tag = n["tag"]
            if n["rect"]["w"] * n["rect"]["h"] == 0: continue
            if n["text"]:
                c = to_hex(s["color"])
                if c: colors["text"][c] += 1            # transparent / gradient text -> no solid colour token
                else: gradient_text = True
                fs_px = px(s["font-size"]); lh_px = px(s["line-height"])
                if fs_px and lh_px: lh_ratio[round(lh_px / fs_px, 2)] += 1
            if "gradient(" in (s.get("background-image") or ""): gradients[s["background-image"][:160]] += 1
            bg = to_hex(s["background-color"])
            if bg: colors["background"][bg] += 1; bg_area[bg] += n["rect"]["w"] * n["rect"]["h"]
            if tag == "body": body_bg = bg; body_text = to_hex(s["color"])
            if s["border-top-style"] not in ("none", "hidden") and px(s["border-top-width"]):
                bc = to_hex(s["border-top-color"]); 
                if bc: colors["border"][bc] += 1
                borders[f'{s["border-top-width"]} {s["border-top-style"]}'] += 1
            if n["text"] or tag in ("input", "textarea", "button", "a"):
                fam = s["font-family"].split(",")[0].strip().strip('"\''); fonts[fam] += 1
                sizes[s["font-size"]] += 1; weights[s["font-weight"]] += 1; lh[s["line-height"]] += 1
                if s["letter-spacing"] != "normal": ls[s["letter-spacing"]] += 1
                if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "button", "label", "li", "span", "small"):
                    type_combos[(tag, fam, s["font-size"], s["font-weight"], s["line-height"])] += 1
            for p in ("padding-top", "padding-right", "padding-bottom", "padding-left", "margin-top", "margin-bottom"):
                v = px(s[p]); 
                if v and v > 0: spacing[int(v) if v.is_integer() else v] += 1
            for p in ("gap", "row-gap", "column-gap"):
                v = s[p].split()[0] if s[p] else ""; vv = px(v)
                if vv and vv > 0: gaps[int(vv) if vv.is_integer() else vv] += 1
            r = s["border-top-left-radius"]
            if r and r != "0px": radii[r] += 1
            if s["box-shadow"] and s["box-shadow"] != "none": shadows[s["box-shadow"]] += 1
            if s["z-index"] not in ("auto", "0"): zidx[s["z-index"]] += 1
            if s["transition-duration"] and s["transition-duration"] not in ("0s", "") and s["transition-property"] not in ("all", "none") or (s["transition-duration"] not in ("0s", "") and s["transition-property"] == "all"):
                durations[split_top(s["transition-duration"])[0]] += 1; easings[(split_top(s["transition-timing-function"]) or ["ease"])[0]] += 1
                transitions[(s["transition-property"][:60], (split_top(s["transition-duration"]) or [""])[0], (split_top(s["transition-timing-function"]) or ["ease"])[0])] += 1
            if s["animation-name"] and s["animation-name"] != "none":
                durations[(split_top(s["animation-duration"]) or [""])[0]] += 1
            mw = px(s["max-width"]); 
            if mw and mw >= 480 and tag in ("div", "main", "section", "header", "footer", "nav", "article"): widths[int(mw)] += 1
    # Breakpoints from media queries
    bps = Counter()
    cqs = Counter()
    for cap in caps:
        for q, n in (cap.get("containerQueries") or {}).items(): cqs[q] += n
    for cap in caps:
        for q, n in (cap.get("mediaQueries") or {}).items():
            for m in re.finditer(r'(min|max)-width:\s*([\d.]+)(px|em|rem)', q):
                v = float(m[2]) * (16 if m[3] in ("em", "rem") else 1); bps[(m[1], int(v))] += n
    all_colors = Counter()
    for role in colors:
        if None in colors[role]: del colors[role][None]
        all_colors.update(colors[role])
    # second pass: contrast of text colours against the background they actually sit on
    for cap in caps:
        by_id = {n["id"]: n for n in cap.get("nodes", [])}
        for n in cap.get("nodes", []):
            if not n["text"]: continue
            c = to_hex(n["styles"]["color"])
            if not c or len(c) != 7: continue
            bg = None; cur = n; skip = False
            while cur is not None and bg is None:
                bi = cur["styles"].get("background-image") or ""
                if "gradient(" in bi or "url(" in bi: skip = True; break   # text sits on a gradient/image; contrast not meaningful here
                b = to_hex(cur["styles"]["background-color"]); bg = b if b and len(b) == 7 else None
                cur = by_id.get(cur["parent"]) if cur["parent"] is not None else None
            if skip: continue
            bg = bg or "#ffffff"; ratio = contrast(c, bg); size = px(n["styles"]["font-size"]) or 16; bold = n["styles"]["font-weight"] in ("700", "800", "900", "bold")
            large = size >= 24 or (size >= 18.66 and bold)
            if ratio < (3 if large else 4.5):
                k = (c, bg); low_contrast.setdefault(k, {"hex": c, "onBackground": bg, "contrast": ratio, "elements": 0, "sample": n["text"][:40]}); low_contrast[k]["elements"] += 1
    area_sorted = bg_area.most_common(1); text_sorted = colors["text"].most_common(1)
    page_bg = body_bg or (area_sorted[0][0] if area_sorted else "#ffffff"); page_text = body_text or (text_sorted[0][0] if text_sorted else "#000000")
    def rank(counter, keyfn=lambda k: k):
        return [{"value": keyfn(k), "uses": c, "props": sorted(prop_by_value.get(str(keyfn(k)).lower(), []))[:4]} for k, c in counter.most_common(40)]
    palette = [{"hex": h, "uses": c, "roles": {r: colors[r][h] for r in colors if colors[r][h]}, "contrastOnPageBg": contrast(h, page_bg) if len(h) == 7 else None, "props": sorted(prop_by_value.get(h, []))[:4]} for h, c in all_colors.most_common(48)]
    def is_neutral(h):
        if len(h) < 7: return False
        ch = [int(h[i:i+2], 16) for i in (1, 3, 5)]; chroma = max(ch) - min(ch); lum = (max(ch) + min(ch)) / 510
        return chroma < 24 or lum < 0.12 or lum > 0.93
    neutral = [p for p in palette if is_neutral(p["hex"])]
    accent = [p for p in palette if p not in neutral]
    sp_vals = sorted(spacing.items(), key=lambda kv: -kv[1])
    base_guess = None
    for cand in (4, 8, 5, 6):
        top = sp_vals[:12]; tot = sum(c for _, c in top) or 1
        if len(top) >= 4 and sum(c for v, c in top if v % cand == 0) / tot >= 0.6: base_guess = cand; break
    return {
        "source": [c.get("url") for c in caps], "viewports": [c.get("viewport") for c in caps],
        "modern": {"shadowDom": any((c.get("shadow") or {}).get("hosts") for c in caps), "shadowHosts": max(((c.get("shadow") or {}).get("hosts") or 0) for c in caps), "customElements": sorted({e for c in caps for e in (c.get("customElements") or [])})[:30], "containerQueries": sum(len(c.get("containerQueries") or {}) for c in caps), "colorScheme": caps[0].get("theme", {}).get("colorScheme")},
        "page": {"background": page_bg, "text": page_text, "colorScheme": caps[0].get("theme"), "lang": caps[0].get("lang")},
        "colors": {"accent": accent[:16], "neutral": neutral[:16], "byRole": {r: rank(colors[r]) [:12] for r in colors}},
        "typography": {"families": rank(fonts), "sizes": rank(sizes), "weights": rank(weights), "lineHeights": rank(lh)[:12], "lineHeightRatios": rank(lh_ratio)[:6], "letterSpacing": rank(ls)[:8],
                        "scale": [{"tag": t, "family": f, "size": sz, "weight": w, "lineHeight": l, "uses": c} for (t, f, sz, w, l), c in type_combos.most_common(24)],
                        "fontFaces": caps[0].get("fontFaces", [])[:24], "loaded": sorted({f["family"] for c in caps for f in c.get("loadedFonts", [])}), "gradientText": gradient_text},
        "spacing": {"baseUnitGuess": base_guess, "values": rank(spacing)[:20], "gaps": rank(gaps)[:12]},
        "radii": rank(radii)[:10], "shadows": rank(shadows)[:10], "borders": rank(borders)[:8],
        "layout": {"containerMaxWidths": rank(widths)[:6], "breakpoints": [{"kind": k, "px": v, "rules": n} for (k, v), n in sorted(bps.items(), key=lambda kv: kv[0][1])], "containerQueries": [{"query": q, "rules": n} for q, n in cqs.most_common(12)]},
        "zIndex": rank(zidx)[:12],
        "motion": {"durations": rank(durations)[:8], "easings": rank(easings)[:8], "transitions": [{"property": p, "duration": d, "easing": e, "uses": c} for (p, d, e), c in transitions.most_common(12)], "keyframes": list((caps[0].get("keyframes") or {}).keys())[:30]},
        "gradients": rank(gradients)[:8],
        "accessibility": {"lowContrastText": sorted(low_contrast.values(), key=lambda x: -x["elements"])[:12], "note": "WCAG AA: 4.5:1 normal text, 3:1 large text (>=24px or >=18.66px bold). Background is the nearest ancestor with an opaque colour; gradients and images are not evaluated."},
        "rare": {"colors": [h for h, c in all_colors.items() if c < min_uses][:40]},
        "limitations": ["Counts are per visible element in the captured viewport(s); hidden states (hover, open menus) are not included unless captured with --hover/--click.",
                        "Computed values lose the author's intent; a custom property listed in 'props' is the closest thing to the original token name.",
                        "Base-unit guess is a divisibility heuristic over the most frequent paddings/margins."]
    }

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def color_name(c, fallback):
    n = c["props"][0].lstrip("-") if c["props"] else fallback
    return re.sub(r'^(color|colour|clr|c)-', '', slug(n)) or fallback

def write_outputs(tokens, out, min_uses):
    os.makedirs(out, exist_ok=True)
    json.dump(tokens, open(os.path.join(out, "tokens.json"), "w", encoding="utf-8"), indent=1)
    css = [":root {"]; tw = {"colors": {}, "fontFamily": {}, "fontSize": {}, "borderRadius": {}, "boxShadow": {}, "spacing": {}, "screens": {}, "transitionDuration": {}}
    for i, c in enumerate([p for p in tokens["colors"]["accent"] if p["uses"] >= min_uses][:8]):
        name = color_name(c, f"accent-{i+1}"); css.append(f"  --color-{name}: {c['hex']}; /* {c['uses']} uses */"); tw["colors"][name] = c["hex"]
    for i, c in enumerate([p for p in tokens["colors"]["neutral"] if p["uses"] >= min_uses][:10]):
        name = color_name(c, f"neutral-{i+1}"); css.append(f"  --color-{name}: {c['hex']}; /* {c['uses']} uses */"); tw["colors"][name] = c["hex"]
    for i, f in enumerate(tokens["typography"]["families"][:3]):
        key = ["sans", "secondary", "mono"][i] if i < 3 else f"font-{i}"; css.append(f'  --font-{key}: "{f["value"]}";'); tw["fontFamily"][key] = [f["value"]]
    for s in [x for x in tokens["typography"]["sizes"] if x["uses"] >= min_uses][:10]:
        k = "text-" + s["value"].replace("px", ""); css.append(f"  --{k}: {s['value']};"); tw["fontSize"][s["value"].replace("px", "")] = s["value"]
    for s in [x for x in tokens["spacing"]["values"] if x["uses"] >= min_uses][:12]:
        css.append(f"  --space-{s['value']}: {s['value']}px;"); tw["spacing"][str(s["value"])] = f"{s['value']}px"
    for i, r in enumerate([x for x in tokens["radii"] if x["uses"] >= min_uses][:6]):
        css.append(f"  --radius-{i+1}: {r['value']};"); tw["borderRadius"][f"r{i+1}"] = r["value"]
    for i, sh in enumerate([x for x in tokens["shadows"] if x["uses"] >= min_uses][:5]):
        css.append(f"  --shadow-{i+1}: {sh['value']};"); tw["boxShadow"][f"s{i+1}"] = sh["value"]
    for b in tokens["layout"]["breakpoints"]:
        if b["kind"] == "min-width": tw["screens"][f"bp{b['px']}"] = f"{b['px']}px"
    for d in tokens["motion"]["durations"][:4]:
        css.append(f"  --duration-{slug(d['value'])}: {d['value']};"); tw["transitionDuration"][slug(d["value"])] = d["value"]
    css.append("}")
    open(os.path.join(out, "tokens.css"), "w", encoding="utf-8").write("\n".join(css) + "\n")
    open(os.path.join(out, "tailwind.theme.js"), "w", encoding="utf-8").write("// Paste into tailwind.config.js -> theme.extend\nmodule.exports = " + json.dumps({k: v for k, v in tw.items() if v}, indent=2) + ";\n")

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    out = None; min_uses = 2; paths = []; as_json = False
    i = 0
    while i < len(argv):
        if argv[i] == "--out": out = argv[i+1]; i += 2
        elif argv[i] == "--min-uses": min_uses = int(argv[i+1]); i += 2
        elif argv[i] == "--json": as_json = True; i += 1
        else: paths.append(argv[i]); i += 1
    caps = load_captures(paths)
    tokens = extract(caps, min_uses)
    out = out or (paths[0] if os.path.isdir(paths[0]) else os.path.dirname(os.path.abspath(paths[0])))
    write_outputs(tokens, out, min_uses)
    if as_json: print(json.dumps(tokens, indent=1)); return 0
    t = tokens
    print(f"Page: bg {t['page']['background']}  text {t['page']['text']}  fonts {', '.join(t['typography']['loaded'][:5])}")
    print("Accent colors:", ", ".join(f"{c['hex']}({c['uses']})" for c in t["colors"]["accent"][:8]))
    print("Neutrals:     ", ", ".join(f"{c['hex']}({c['uses']})" for c in t["colors"]["neutral"][:8]))
    print("Type sizes:   ", ", ".join(f"{s['value']}({s['uses']})" for s in t["typography"]["sizes"][:8]))
    print("Spacing:      ", f"base≈{t['spacing']['baseUnitGuess']}px;", ", ".join(f"{s['value']}({s['uses']})" for s in t["spacing"]["values"][:10]))
    print("Radii:        ", ", ".join(f"{r['value']}({r['uses']})" for r in t["radii"][:6]))
    print("Breakpoints:  ", ", ".join(f"{b['kind']} {b['px']}px" for b in t["layout"]["breakpoints"][:8]))
    low = t["accessibility"]["lowContrastText"]
    if low: print("Low contrast: ", ", ".join(f"{c['hex']} on {c['onBackground']} = {c['contrast']} ({c['elements']} el.)" for c in low[:4]))
    if t["gradients"]: print("Gradients:    ", t["gradients"][0]["value"][:90])
    print("Motion:       ", ", ".join(f"{d['value']}({d['uses']})" for d in t["motion"]["durations"][:5]), "|", ", ".join(e["value"] for e in t["motion"]["easings"][:3]))
    print(f"\nWrote tokens.json, tokens.css, tailwind.theme.js to {out}")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

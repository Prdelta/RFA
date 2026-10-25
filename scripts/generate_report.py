#!/usr/bin/env python3
"""generate_report.py - pre-fill the report template from script outputs.

Usage:
    python3 generate_report.py --capture <dir> [--stack stack.json] [--tokens tokens.json]
                               [--components components.json] [--whitelabel whitelabel.json]
                               [--parity parity.json ...] [--state-diff diff.json ...]
                               [--out report.md] [--title "Name"]

Reads whatever you give it and writes a Markdown report following
assets/report-template.md with the measured sections filled in (target, stack,
tokens, components, breakpoints, motion, parity, limitations). Sections that
need judgment (layout narrative, reconstruction mapping, licensing decisions)
are left as clearly marked TODO lines so the agent fills them rather than
shipping a template. Standard library only.
"""
import json, os, sys, datetime

def rd(p): return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else None

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    opts = {"parity": [], "state-diff": []}; i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        if k in ("parity", "state-diff"): opts[k].append(argv[i + 1]); i += 2
        else: opts[k] = argv[i + 1]; i += 2
    cap_dir = opts.get("capture"); summary = rd(os.path.join(cap_dir, "summary.json")) if cap_dir else None
    caps = []
    if cap_dir:
        for root, _, files in os.walk(cap_dir):
            if "capture.json" in files: caps.append((root, rd(os.path.join(root, "capture.json"))))
    stack = rd(opts.get("stack")); tokens = rd(opts.get("tokens")); comps = rd(opts.get("components")); wl = rd(opts.get("whitelabel"))
    parity = [rd(p) for p in opts["parity"]]; diffs = [rd(p) for p in opts["state-diff"]]
    title = opts.get("title") or (caps[0][1].get("title") if caps else "target")
    L = []; add = L.append
    add(f"# Frontend reverse-engineering report: {title}\n")
    add("## 1. Target and scope")
    add(f"- URL / file: {summary['target'] if summary else (caps[0][1]['url'] if caps else 'TODO')}   Captured: {summary['capturedAt'][:10] if summary else datetime.date.today()}")
    add(f"- Viewports: {', '.join(v['viewport'] for v in summary['viewports']) if summary else ', '.join(f'{c[1]['viewport']['w']}x{c[1]['viewport']['h']}' for _, c in caps)}")
    add("- Asked for: TODO (whole page | component | tokens | interaction)")
    add("- Target stack for the rebuild: TODO")
    states = sorted({" ".join(c.get("stateActions") or ["resting"]) for _, c in caps})
    add(f"- Captured states: {', '.join(states) or 'resting'}")
    trunc = [os.path.basename(r) for r, c in caps if c.get("truncated")]
    add(f"- Not captured: TODO (auth-only pages, error states, gestures){'; truncated node list at ' + ', '.join(trunc) if trunc else ''}\n")
    add("## 2. Stack detection")
    if stack:
        add("| Category | Finding | Confidence | Evidence |\n| -------- | ------- | ---------- | -------- |")
        for f in stack["findings"]: add(f"| {f['category']} | {f['name']} | {f['confidence']} | `{f['evidence'][0][:80].replace('|', '/')}` |")
        add(f"\nRendering mode: {stack['renderingMode']}   Source maps referenced: {stack['sourceMapsReferenced']}\n")
    else: add("TODO: run detect_stack.py and paste findings\n")
    add("## 3. Design tokens")
    if tokens:
        pg = tokens["page"]; add(f"Page background {pg['background']}, text {pg['text']}, lang {pg.get('lang')}.\n")
        add("| Role | Hex | Uses | Contrast on bg | Original name |\n| ---- | --- | ---- | -------------- | ------------- |")
        for c in tokens["colors"]["accent"][:8]: add(f"| accent ({', '.join(c['roles'])}) | {c['hex']} | {c['uses']} | {c['contrastOnPageBg']} | {', '.join(c['props']) or '-'} |")
        for c in tokens["colors"]["neutral"][:8]: add(f"| neutral ({', '.join(c['roles'])}) | {c['hex']} | {c['uses']} | {c['contrastOnPageBg']} | {', '.join(c['props']) or '-'} |")
        ty = tokens["typography"]
        add(f"\nFonts loaded: {', '.join(ty['loaded']) or 'none reported (fallbacks in use?)'}. Families by use: {', '.join(f['value'] + ' (' + str(f['uses']) + ')' for f in ty['families'][:3])}.")
        if ty.get("fontFaces"): add("@font-face sources: " + "; ".join(f"{f['family']} {f['weight']} from {f['src'][:60]}" for f in ty["fontFaces"][:4]) + "   TODO: licence check")
        add("\n| Tag | Family | Size | Weight | Line height | Uses |\n| --- | ------ | ---- | ------ | ----------- | ---- |")
        for s in ty["scale"][:10]: add(f"| {s['tag']} | {s['family']} | {s['size']} | {s['weight']} | {s['lineHeight']} | {s['uses']} |")
        sp = tokens["spacing"]; add(f"\nSpacing base unit ≈ {sp['baseUnitGuess']}px; values: " + ", ".join(f"{v['value']}({v['uses']})" for v in sp["values"][:10]))
        add("Radii: " + ", ".join(f"{r['value']}({r['uses']})" for r in tokens["radii"][:6]) + "   Shadows: " + str(len(tokens["shadows"])) + " distinct   Borders: " + ", ".join(b["value"] for b in tokens["borders"][:3]))
        lay = tokens["layout"]; add("Breakpoints: " + ", ".join(f"{b['kind']} {b['px']}px ({b['rules']} rules)" for b in lay["breakpoints"][:8]) + "   Container widths: " + ", ".join(str(w["value"]) + "px" for w in lay["containerMaxWidths"][:3]))
        mo = tokens["motion"]; add("Motion: durations " + ", ".join(d["value"] for d in mo["durations"][:5]) + "; easings " + ", ".join(e["value"] for e in mo["easings"][:3]) + "; keyframes " + ", ".join(mo["keyframes"][:8]))
        if tokens.get("gradients"): add("Gradients: " + "; ".join(g["value"][:70] for g in tokens["gradients"][:4]))
        low = tokens.get("accessibility", {}).get("lowContrastText") or []
        if low: add("Low-contrast text colours (< 4.5:1): " + ", ".join(f"{c['hex']} ({c['contrast']})" for c in low[:6]))
        add("")
    else: add("TODO: run extract_tokens.py\n")
    add("## 4. Component inventory")
    if comps:
        for c in comps["candidates"][:20]:
            add(f"### {c['name']}\nSelector hint `{c['selectorHint']}` · {c['instances']} instance(s) · box {c['box']['w'][0]}-{c['box']['w'][1]} x {c['box']['h'][0]}-{c['box']['h'][1]}")
            cs = c["commonStyles"]; add("Styles: " + "; ".join(f"{k} {v}" for k, v in list(cs.items())[:8]))
            if c["children"]: add("Children: " + ", ".join(f"{k} x{v}" for k, v in c["children"].items()))
            if c["variants"]: add("Variants: " + "; ".join(f"{k} " + "/".join(f"{v}({n})" for v, n in d.items()) for k, d in c["variants"].items()))
            if c["interaction"]: add("Interaction: " + ", ".join(c["interaction"]))
            if c["a11y"]: add("A11y: " + "; ".join(c["a11y"]))
            add("Rebuild: TODO file\n")
    else: add("TODO: run inventory_components.py --json and describe each component\n")
    add("## 5. Layout and responsive rules\nTODO: per breakpoint, what changes (compare captures across viewports with diff_captures.py --mode parity).\n")
    add("## 6. Motion and interaction\n| What | Trigger | Properties | Duration | Easing | Source |\n| ---- | ------- | ---------- | -------- | ------ | ------ |")
    for d in diffs:
        trig = " ".join(d.get("stateActions", [None, None])[1] or ["?"])
        for c in d.get("changes", [])[:8]:
            tr = c.get("transition") or {}
            add(f"| {c['node'][:30]} | {trig} | {', '.join(c['changed'])[:40]} | {tr.get('transition-duration', 'n/a')} | {tr.get('transition-timing-function', 'n/a')} | {'CSS transition' if tr else 'script/instant'} |")
    for _, c in caps:
        for name, steps in list((c.get("keyframes") or {}).items())[:6]: add(f"| @keyframes {name} | load/class | {steps[0]['style'][:40] if steps else ''} | see nodes | | CSS keyframes |")
    add("\n## 7. Reconstruction\nTODO: files written, original selector each derives from, tokens file, dependencies added.\n")
    add("## 8. Parity check")
    if parity:
        add("| Viewport/pair | pixelMatch | perceptual | Same size | Main differences |\n| ------------- | ---------- | ---------- | --------- | ---------------- |")
        for p in parity: add(f"| {os.path.basename(os.path.dirname(p['a']))} | {p['pixelMatch']*100:.1f}% | {p['perceptual']*100:.1f}% | {p['sameSize']} | {len(p['regions'])} regions, worst {p['regions'][0]['box'] if p['regions'] else '-'} |")
    else: add("TODO: capture the rebuild at the same viewports and run compare_screenshots.py --json and diff_captures.py --mode parity")
    add("\nChecklist: structure ☐ · typography ☐ · spacing ☐ · breakpoints ☐ · states ☐ · keyboard ☐ · reduced motion ☐\n")
    add("## 9. Unknowns and limitations")
    for r, c in caps:
        unread = [s["href"] for s in c.get("stylesheets", []) if not s.get("readable")]
        if unread: add(f"- {os.path.basename(r)}: {len(unread)} cross-origin stylesheet(s) not readable (rules applied but text unavailable): {unread[0][:80]}")
        if c.get("consoleErrors"): add(f"- {os.path.basename(r)}: {len(c['consoleErrors'])} page error(s) during capture")
        if c.get("truncated"): add(f"- {os.path.basename(r)}: node list truncated; narrow with --selector")
    add("- States not captured: TODO\n- Estimates (script-driven motion timings, pixel-read values from images): TODO\n")
    add("## 10. White-label template")
    if wl:
        add(f"- Brand name lifted to `--brand-name`: {wl.get('brandName')} -> {{{{BRAND_NAME}}}}")
        add("- Theming contract (flip to re-skin): " + ", ".join(f"`{v}`" for v in wl.get("themingContract", [])))
        add("- Neutral default theme shipped; captured theme kept for parity only.")
        a = wl.get("assetsToReplace", {}); add(f"- Assets to replace: {a.get('logos',0)} logo(s), {a.get('favicons',0)} favicon(s), {a.get('images',0)} image(s), {a.get('copyBlocks',0)} copy block(s)")
        add("- Fonts: " + "; ".join(f"{f['family']} -> {f['openSubstitute']}{' (self-hosted/paid)' if f.get('selfHostedOrPaid') else ''}" for f in wl.get("fonts", [])))
        g = wl.get("genericScaleCarriedOver", {}); add(f"- Generic scale carried into the template: radius {g.get('radius')}, spacing base {g.get('spacingBasePx')}px, breakpoints {g.get('breakpoints')}")
        add("- Verify neutral: grep components for captured hues/fonts/name/assets (expect zero); apply a second theme and re-screenshot.\n")
    else: add("TODO: run whitelabel.py --json and summarise the brand.config, theming contract and assets to replace\n")
    add("## 11. Licensing notes\n- Fonts: TODO (source, licence, substitute)\n- Icons / images: TODO\n- Brand elements deliberately not copied: TODO\n")
    out = opts.get("out") or (os.path.join(cap_dir, "report.md") if cap_dir else "report.md")
    open(out, "w", encoding="utf-8").write("\n".join(L)); print("wrote", out)
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

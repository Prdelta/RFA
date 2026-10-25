#!/usr/bin/env python3
"""inventory_components.py - find repeated structures in a capture and describe
them as component candidates with variants, states hints and a11y notes.

Usage:
    python3 inventory_components.py <capture.json|dir> [--min-instances 2] [--max-depth 3] [--markdown] [--json]

How it works: elements with an author-named class (card, Button_root__x1,
not css-1abc hashes) group by tag + class root. Elements without one get a
shape signature made of the tag, the children's tag sequence (to
--max-depth) and the box styling (display, padding, radius, border, shadow). Elements sharing a signature
with --min-instances or more occurrences become a candidate. Landmarks
(header, nav, main, footer, dialog, role=*) are listed even when unique.
For each candidate the script reports the common styles, the properties that
vary between instances (variants), text/aria attributes, and interaction
hints (transitions, cursor pointer, aria-expanded...).

Candidates are starting points; merge or split them by judgment. Standard
library only.
"""
import json, os, sys, re
from collections import defaultdict, Counter

def load(p):
    if os.path.isdir(p):
        for root, _, files in os.walk(p):
            if "capture.json" in files: p = os.path.join(root, "capture.json"); break
    return json.load(open(p, encoding="utf-8"))

BOX_KEYS = ["display", "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-left-radius", "border-top-width", "border-top-style", "box-shadow", "background-color", "flex-direction", "gap", "grid-template-columns"]
VARIANT_KEYS = BOX_KEYS + ["color", "border-top-color", "font-size", "font-weight", "width", "height", "opacity", "transform", "background-image"]
LANDMARK_TAGS = {"header", "nav", "main", "footer", "aside", "form", "dialog", "table"}

def class_root(cls):
    toks = [t for t in (cls or "").split() if not re.match(r'^(css-|sc-|_|[a-z]+:)', t) and len(t) > 2]
    toks = [re.sub(r'(__|_|-)[A-Za-z0-9]{5,}$', '', t) for t in toks]
    return toks[0] if toks else ""

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    cap = load(argv[0]); min_inst = 2; max_depth = 3; md = "--markdown" in argv; as_json = "--json" in argv
    if "--min-instances" in argv: min_inst = int(argv[argv.index("--min-instances") + 1])
    if "--max-depth" in argv: max_depth = int(argv[argv.index("--max-depth") + 1])
    nodes = cap["nodes"]; by_id = {n["id"]: n for n in nodes}; children = defaultdict(list)
    for n in nodes: children[n["parent"]].append(n)
    def shape(n, depth):
        if depth == 0 or not children[n["id"]]: return n["tag"]
        return n["tag"] + "(" + ",".join(shape(c, depth - 1) for c in children[n["id"]][:12]) + ")"
    def sig(n):
        root = class_root(n["attrs"].get("class"))
        if root: return n["tag"] + "." + root   # author-named class: same component, variants differ in styles
        s = n["styles"]; box = "|".join(s.get(k, "") for k in ("display", "padding-top", "padding-left", "border-top-left-radius", "border-top-width", "box-shadow"))
        return shape(n, max_depth) + "#" + box
    groups = defaultdict(list)
    for n in nodes:
        if n["tag"] in ("html", "body", "script", "style", "br", "path", "g", "circle", "rect", "line", "polyline", "use", "defs"): continue
        if n["rect"]["w"] < 16 or n["rect"]["h"] < 8: continue
        groups[sig(n)].append(n)
    def describe(group, name_hint):
        s0 = group[0]["styles"]; common = {}; variants = {}
        for k in VARIANT_KEYS:
            vals = Counter(n["styles"].get(k) for n in group)
            if len(vals) == 1: common[k] = s0.get(k)
            elif len(vals) <= max(3, len(group) // 2): variants[k] = {v: c for v, c in vals.most_common(4)}
        boxes = [(n["rect"]["w"], n["rect"]["h"]) for n in group]
        ws = sorted(b[0] for b in boxes); hs = sorted(b[1] for b in boxes)
        texts = [n["text"] for n in group if n["text"]][:4]
        aria = Counter(); inter = Counter()
        def collect(n, d=0):
            for k, v in n["attrs"].items():
                if k.startswith("aria-") or k in ("role", "tabindex", "alt", "href", "type", "placeholder"): aria[k] += 1
            st = n["styles"]
            if st.get("cursor") == "pointer": inter["cursor:pointer"] += 1
            if st.get("transition-duration") not in (None, "", "0s"): inter["transition " + st.get("transition-property", "")[:40] + " " + st.get("transition-duration", "").split(",")[0]] += 1
            if st.get("animation-name") not in (None, "none"): inter["animation " + st["animation-name"]] += 1
            if n["attrs"].get("aria-expanded") is not None: inter["aria-expanded (toggle)"] += 1
            if n["attrs"].get("data-state"): inter["data-state=" + n["attrs"]["data-state"]] += 1
            if d < 3:
                for c in children[n["id"]]: collect(c, d + 1)
        for n in group: collect(n)
        tags_inside = Counter()
        for n in group:
            for c in children[n["id"]]: tags_inside[c["tag"] + ("." + class_root(c["attrs"].get("class")) if class_root(c["attrs"].get("class")) else "")] += 1
        a11y = []
        clickable = any(n["styles"].get("cursor") == "pointer" for n in group)
        if clickable and group[0]["tag"] in ("div", "span") and not group[0]["attrs"].get("role"): a11y.append("clickable div/span without role (use button or a)")
        if group[0]["tag"] == "img" and not all(n["attrs"].get("alt") for n in group): a11y.append("img without alt")
        if group[0]["tag"] in ("input", "textarea", "select") and not any(k in aria for k in ("aria-label", "placeholder")): a11y.append("form control without aria-label (check for <label>)")
        if group[0]["tag"] == "a" and not all(n["attrs"].get("href") for n in group): a11y.append("anchor without href")
        return {"name": name_hint, "tag": group[0]["tag"], "instances": len(group), "selectorHint": (group[0]["tag"] + ("." + class_root(group[0]["attrs"].get("class")) if class_root(group[0]["attrs"].get("class")) else "")),
                "box": {"w": [ws[0], ws[-1]], "h": [hs[0], hs[-1]]}, "positions": [[n["rect"]["x"], n["rect"]["y"]] for n in group[:6]],
                "commonStyles": {k: v for k, v in common.items() if v not in (None, "", "none", "0px", "normal", "auto", "rgba(0, 0, 0, 0)", "static", "visible")},
                "variants": variants, "children": dict(tags_inside.most_common(8)), "sampleText": texts, "attrs": dict(aria.most_common(8)), "interaction": dict(inter.most_common(6)), "a11y": a11y}
    cands = []
    for k, g in groups.items():
        if len(g) >= min_inst:
            root = class_root(g[0]["attrs"].get("class")); name = root or g[0]["tag"]
            cands.append(describe(g, name))
    for n in nodes:
        role = n["attrs"].get("role")
        if (n["tag"] in LANDMARK_TAGS or role in ("dialog", "navigation", "banner", "tablist", "menu", "search", "contentinfo")) and n["rect"]["w"] > 40:
            cands.append(describe([n], n["tag"] if not role else f'{n["tag"]}[role={role}]'))
    # Drop candidates fully nested within another candidate with the same instance count and no own styling (wrapper noise)
    cands.sort(key=lambda c: (-c["instances"] * c["box"]["w"][1] * c["box"]["h"][1]))
    seen = set(); out = []
    for c in cands:
        key = (c["name"], c["tag"], c["instances"], tuple(sorted(c["children"].items())))
        if key in seen: continue
        seen.add(key); out.append(c)
    res = {"url": cap.get("url"), "viewport": cap.get("viewport"), "candidates": out[:40], "note": "Shape signatures group by tag, child tag sequence and box styling. Merge groups that are the same component with different content; split groups that merely look alike."}
    if as_json: print(json.dumps(res, indent=1)); return 0
    for c in res["candidates"]:
        if md:
            print(f"### {c['name']}\nSelector hint: `{c['selectorHint']}`   Instances: {c['instances']}   Box: {c['box']['w'][0]}-{c['box']['w'][1]} x {c['box']['h'][0]}-{c['box']['h'][1]}")
            cs = c["commonStyles"]; print("Styles: " + "; ".join(f"{k} {v}" for k, v in list(cs.items())[:9]))
            if c["children"]: print("Children: " + ", ".join(f"{k} x{v}" for k, v in c["children"].items()))
            if c["variants"]: print("Variants: " + "; ".join(f"{k} " + "/".join(f"{v}({n})" for v, n in d.items()) for k, d in c["variants"].items()))
            if c["interaction"]: print("Interaction: " + ", ".join(c["interaction"]))
            if c["attrs"]: print("Attrs: " + ", ".join(c["attrs"]))
            if c["a11y"]: print("A11y: " + "; ".join(c["a11y"]))
            if c["sampleText"]: print("Text: " + " | ".join(c["sampleText"]))
            print()
        else:
            print(f"{c['name']:<22} <{c['tag']}> x{c['instances']:<3} {c['box']['w'][0]}-{c['box']['w'][1]}x{c['box']['h'][0]}-{c['box']['h'][1]:<5} children: {', '.join(c['children'])[:50]:<52} {'VARIANTS: ' + ','.join(c['variants']) if c['variants'] else ''}")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""diff_captures.py - compare two capture.json files node by node.

Usage:
    python3 diff_captures.py <a.json|dir> <b.json|dir> [--mode state|parity] [--selector-prefix tag] [--json]

Two situations, one tool:

  --mode state   (default) A and B are the SAME page in two states (resting vs
                 hover, closed vs open, light vs dark, scroll 0 vs 600). Nodes
                 are matched by their structural path and the output lists, per
                 node, every computed property that changed with old -> new
                 values plus the transition declared on that node. This is how
                 you measure what a hover or a click actually does.

  --mode parity  A is the ORIGINAL and B is your REBUILD. Nodes are matched by
                 path too, but the report is organised as: structure (tags
                 missing/extra per depth), typography mismatches, box mismatches
                 (padding, radius, border, shadow, gap), colour mismatches, and
                 layout mismatches (rect width/height off by more than 2px).

Matching key: tag + nth-of-type index along the ancestor chain, with id or
data-testid used when present. Hashed class names are ignored on purpose.
Standard library only.
"""
import json, os, sys
from collections import Counter, defaultdict

import re as _re
def _canon_color(v):
    """rgba()/rgb()/color(srgb ...) for the same colour serialise differently
    across engines and color-mix(); canonicalise to rgb(R,G,B,A 0-255) so the
    diff compares colours, not spellings."""
    if not isinstance(v, str): return v
    def repl(m):
        nums = _re.findall(r'[-\d.]+', m.group(0))
        if m.group(0).startswith('color('):
            parts = nums[-4:] if '/' in m.group(0) else nums[-3:]
            try: rgb = [max(0, min(255, round(float(x) * 255))) for x in parts[:3]]; a = round(float(parts[3]) * 255) if len(parts) > 3 else 255
            except Exception: return m.group(0)
        else:
            try: rgb = [int(float(x)) for x in nums[:3]]; a = round(float(nums[3]) * 255) if len(nums) > 3 else 255
            except Exception: return m.group(0)
        return f"rgb({rgb[0]},{rgb[1]},{rgb[2]},{a})"
    return _re.sub(r'(rgba?\([^)]*\)|color\(srgb[^)]*\))', repl, v)
def _canon(k, v):
    if k == "font-family" and isinstance(v, str):
        return v.split(",")[0].strip().strip('"\'').lower()   # compare the primary family, not the fallback tail
    if isinstance(v, str) and ("rgb" in v or "color(" in v): return _canon_color(v)
    return v

def load(p):
    if os.path.isdir(p):
        for root, _, files in os.walk(p):
            if "capture.json" in files: p = os.path.join(root, "capture.json"); break
    return json.load(open(p, encoding="utf-8"))

def build_paths(cap):
    nodes = cap["nodes"]; by_id = {n["id"]: n for n in nodes}
    children = defaultdict(list)
    for n in nodes: children[n["parent"]].append(n)
    paths = {}
    def walk(n, prefix):
        a = n["attrs"]
        if a.get("data-testid"): key = f'[{a["data-testid"]}]'
        elif a.get("id") and not any(ch.isdigit() for ch in a["id"][-4:]): key = f'#{a["id"]}'
        else:
            sibs = [s for s in children[n["parent"]] if s["tag"] == n["tag"]]
            idx = sibs.index(n) + 1 if n in sibs else 1
            key = f'{n["tag"]}:{idx}'
        p = prefix + "/" + key; paths[p] = n
        for c in children[n["id"]]: walk(c, p)
    roots = [n for n in nodes if n["parent"] is None]
    for r in roots: walk(r, "")
    return paths

TYPO = ["font-family", "font-size", "font-weight", "line-height", "letter-spacing", "text-transform", "text-align"]
BOX = ["padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-left-radius", "border-top-width", "border-top-style", "box-shadow", "gap", "margin-top", "margin-bottom"]
COLOR = ["color", "background-color", "border-top-color", "background-image"]
LAYOUT = ["display", "position", "flex-direction", "justify-content", "align-items", "grid-template-columns", "max-width", "width", "height"]
NOISE = {"transition-delay", "animation-delay", "cursor", "pointer-events"}

def label(n):
    a = n["attrs"]; cls = (a.get("class") or "").split()[:2]
    return f'<{n["tag"]}{"#"+a["id"] if a.get("id") else ""}{"."+".".join(cls) if cls else ""}>' + (f' "{n["text"][:30]}"' if n["text"] else "")

def diff_state(pa, pb):
    changed = []
    for p, na in pa.items():
        nb = pb.get(p)
        if not nb: continue
        props = {}
        for k, va in na["styles"].items():
            if k in NOISE: continue
            vb = nb["styles"].get(k)
            if vb is not None and _canon(k, vb) != _canon(k, va): props[k] = [va, vb]
        if "color" in props:   # currentColor-derived properties follow `color`; report the cause, not the echoes
            for k in ("border-top-color", "border-color", "outline-color", "border-right-color", "border-bottom-color", "border-left-color"):
                if props.get(k) == props["color"]: del props[k]
        ra, rb = na["rect"], nb["rect"]
        rect = {k: [ra[k], rb[k]] for k in ("x", "y", "w", "h") if abs(ra[k] - rb[k]) > 1}
        if props or rect:
            changed.append({"path": p, "node": label(na), "changed": props, "rect": rect,
                            "transition": {k: nb["styles"].get(k) for k in ("transition-property", "transition-duration", "transition-timing-function")} if nb["styles"].get("transition-duration") not in (None, "0s", "") else None})
    added = [label(n) + "  " + p for p, n in pb.items() if p not in pa][:40]
    removed = [label(n) + "  " + p for p, n in pa.items() if p not in pb][:40]
    changed.sort(key=lambda c: -(len(c["changed"]) + len(c["rect"])))
    return {"mode": "state", "matched": sum(1 for p in pa if p in pb), "changedNodes": len(changed), "added": added, "removed": removed, "changes": changed[:80]}

def diff_parity(pa, pb):
    depth_a = Counter(); depth_b = Counter()
    for p, n in pa.items(): depth_a[(p.count("/"), n["tag"])] += 1
    for p, n in pb.items(): depth_b[(p.count("/"), n["tag"])] += 1
    structure = []
    for k in sorted(set(depth_a) | set(depth_b)):
        if depth_a[k] != depth_b[k]: structure.append({"depth": k[0], "tag": k[1], "original": depth_a[k], "rebuild": depth_b[k]})
    cats = {"typography": TYPO, "box": BOX, "color": COLOR, "layout": LAYOUT}
    mism = {c: [] for c in cats}; rects = []
    for p, na in pa.items():
        nb = pb.get(p)
        if not nb: continue
        for c, keys in cats.items():
            d = {k: [na["styles"].get(k), nb["styles"].get(k)] for k in keys if _canon(k, na["styles"].get(k)) != _canon(k, nb["styles"].get(k))}
            if d: mism[c].append({"path": p, "node": label(na), "diff": d})
        ra, rb = na["rect"], nb["rect"]
        if abs(ra["w"] - rb["w"]) > 2 or abs(ra["h"] - rb["h"]) > 2: rects.append({"path": p, "node": label(na), "original": [ra["w"], ra["h"]], "rebuild": [rb["w"], rb["h"]]})
    matched = sum(1 for p in pa if p in pb)
    score = {c: round(1 - len(v) / max(1, matched), 3) for c, v in mism.items()}
    return {"mode": "parity", "nodesOriginal": len(pa), "nodesRebuild": len(pb), "matched": matched, "unmatchedOriginal": [label(n) + "  " + p for p, n in pa.items() if p not in pb][:40],
            "structureDifferences": structure[:40], "agreement": score, "mismatches": {c: v[:40] for c, v in mism.items()}, "sizeDifferences": rects[:40],
            "note": "Matching is by structural path; a rebuild that nests elements differently will show as unmatched rather than wrong. Fix structure first, then re-run. Height/width differences cascade to every ancestor; fix the deepest mismatched node first and the layout score follows."}

def main(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"): print(__doc__); return 0
    a, b = load(argv[0]), load(argv[1]); mode = "state"; as_json = "--json" in argv
    if "--mode" in argv: mode = argv[argv.index("--mode") + 1]
    pa, pb = build_paths(a), build_paths(b)
    res = diff_state(pa, pb) if mode == "state" else diff_parity(pa, pb)
    res["a"] = a.get("url"); res["b"] = b.get("url"); res["stateActions"] = [a.get("stateActions"), b.get("stateActions")]
    if as_json: print(json.dumps(res, indent=1)); return 0
    if mode == "state":
        print(f"matched {res['matched']} nodes; {res['changedNodes']} changed; {len(res['added'])} added; {len(res['removed'])} removed  (A: {a.get('stateActions')}  B: {b.get('stateActions')})")
        for c in res["changes"][:25]:
            print(f"\n{c['node']}  {c['path']}")
            for k, (va, vb) in c["changed"].items(): print(f"   {k}: {va}  ->  {vb}")
            for k, (va, vb) in c["rect"].items(): print(f"   rect.{k}: {va}  ->  {vb}")
            if c["transition"]: print(f"   transition: {c['transition']['transition-property']} {c['transition']['transition-duration']} {c['transition']['transition-timing-function']}")
        for s in res["added"][:10]: print("added:", s)
        for s in res["removed"][:10]: print("removed:", s)
    else:
        print(f"original {res['nodesOriginal']} nodes, rebuild {res['nodesRebuild']}, matched {res['matched']}")
        print("agreement:", ", ".join(f"{k} {v*100:.0f}%" for k, v in res["agreement"].items()))
        for s in res["structureDifferences"][:15]: print(f"  structure depth {s['depth']} <{s['tag']}>: original {s['original']} vs rebuild {s['rebuild']}")
        for c, items in res["mismatches"].items():
            for m in items[:6]:
                print(f"  [{c}] {m['node']}  " + "; ".join(f"{k}: {v[0]} -> {v[1]}" for k, v in m["diff"].items()))
        for r in res["sizeDifferences"][:10]: print(f"  [size] {r['node']}  {r['original']} -> {r['rebuild']}")
        if res["unmatchedOriginal"]: print(f"  unmatched original nodes: {len(res['unmatchedOriginal'])} (first: {res['unmatchedOriginal'][0]})")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

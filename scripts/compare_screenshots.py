#!/usr/bin/env python3
"""compare_screenshots.py - measure visual parity between two screenshots
(typically original vs reconstruction at the same viewport).

Usage:
    python3 compare_screenshots.py <a.png> <b.png> [--out diff.png] [--threshold 0.9] [--tolerance 24] [--grid 12] [--allow-size-mismatch] [--json]

Reports:
    pixelMatch      share of pixels whose RGB distance is within --tolerance
    perceptual      1 - mean absolute difference on a 64x64 greyscale downscale
                    (less sensitive to one-pixel shifts and anti-aliasing)
    regions         grid cells (--grid x --grid) ordered by how much they differ,
                    with bounding boxes you can map back to components
    diff image      red overlay where pixels differ (written to --out)

Sizes are normalised by padding the smaller image with white so the diff can
be drawn, but a size mismatch fails the check unless --allow-size-mismatch is
given: a reconstruction that is 300px shorter is not at parity. Requires Pillow.
Exit code 0 when pixelMatch >= --threshold, 3 otherwise (handy in scripts).
"""
import json, sys
try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError:
    sys.exit("Pillow is required: pip install pillow")

def pad_to(img, size):
    if img.size == size: return img
    canvas = Image.new("RGB", size, (255, 255, 255)); canvas.paste(img, (0, 0)); return canvas

def main(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"): print(__doc__); return 0
    a_path, b_path = argv[0], argv[1]; out = None; threshold = 0.9; tol = 24; grid = 12; as_json = False; allow_size = False
    i = 2
    while i < len(argv):
        if argv[i] == "--out": out = argv[i+1]; i += 2
        elif argv[i] == "--threshold": threshold = float(argv[i+1]); i += 2
        elif argv[i] == "--tolerance": tol = int(argv[i+1]); i += 2
        elif argv[i] == "--grid": grid = int(argv[i+1]); i += 2
        elif argv[i] == "--json": as_json = True; i += 1
        elif argv[i] == "--allow-size-mismatch": allow_size = True; i += 1
        else: i += 1
    a = Image.open(a_path).convert("RGB"); b = Image.open(b_path).convert("RGB")
    size = (max(a.width, b.width), max(a.height, b.height)); a2, b2 = pad_to(a, size), pad_to(b, size)
    diff = ImageChops.difference(a2, b2)
    # per-pixel max channel difference
    bands = diff.split(); mx = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), bands[2])
    mask = mx.point(lambda v: 255 if v > tol else 0)
    hist = mask.histogram(); changed = hist[255]; total = size[0] * size[1]
    pixel_match = 1 - changed / total
    ga = a2.convert("L").resize((64, 64), Image.BILINEAR); gb = b2.convert("L").resize((64, 64), Image.BILINEAR)
    gd = ImageChops.difference(ga, gb); perceptual = 1 - (sum(i * c for i, c in enumerate(gd.histogram())) / (64 * 64)) / 255
    regions = []
    cw, ch = size[0] / grid, size[1] / grid
    for gy in range(grid):
        for gx in range(grid):
            box = (int(gx * cw), int(gy * ch), int((gx + 1) * cw), int((gy + 1) * ch))
            cell = mask.crop(box); h = cell.histogram(); frac = h[255] / max(1, cell.width * cell.height)
            if frac > 0.02: regions.append({"box": box, "changedShare": round(frac, 3)})
    regions.sort(key=lambda r: -r["changedShare"])
    if out:
        overlay = a2.copy(); red = Image.new("RGB", size, (255, 0, 0)); overlay = Image.composite(red, overlay, mask.point(lambda v: 160 if v else 0))
        d = ImageDraw.Draw(overlay)
        for r in regions[:8]: d.rectangle(r["box"], outline=(255, 0, 0), width=3)
        overlay.save(out)
    res = {"a": a_path, "b": b_path, "sizeA": a.size, "sizeB": b.size, "sameSize": a.size == b.size, "pixelMatch": round(pixel_match, 4), "perceptual": round(perceptual, 4), "changedPixels": changed, "threshold": threshold, "pass": pixel_match >= threshold and (a.size == b.size or allow_size), "regions": regions[:12], "diffImage": out}
    if as_json: print(json.dumps(res, indent=1))
    else:
        print(f"pixelMatch {res['pixelMatch']*100:.1f}%   perceptual {res['perceptual']*100:.1f}%   sizes {a.size} vs {b.size}   {'PASS' if res['pass'] else 'FAIL'} (threshold {threshold*100:.0f}%{'' if res['sameSize'] else ', size mismatch'})")
        for r in regions[:8]: print(f"  region {r['box']}  {r['changedShare']*100:.0f}% changed")
        if out: print("diff image:", out)
    return 0 if res["pass"] else 3

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""ingest_har.py - turn a HAR capture into a local, renderable copy of a page so
capture_page.js can run on it offline (no network needed).

Usage:
    python3 ingest_har.py <capture.har> --out <dir> [--page-url <url>] [--json]

Why: when the live site is unreachable (restricted network, auth wall, or you
only have a HAR the user exported from DevTools), this reconstructs a local
`index.html` plus every CSS, font, image and script the HAR recorded, rewrites
the references to local files, and writes it all flat into --out. Then:

    node capture_page.js <out>/index.html --out ./rfa/site --full-page --viewport 1440x900

gives you a real browser capture (computed styles, screenshot, tokens) of the
page as it shipped. JavaScript that fetches more at runtime won't run offline,
so dynamic content may be missing; everything the HAR captured is present.

Export a HAR in Chrome/Firefox DevTools: Network tab -> reload the page ->
right-click -> Save all as HAR (or the download icon). Standard library only.
"""
import base64, json, os, re, sys, hashlib
from urllib.parse import urlsplit, urljoin

TEXT_MIME = ("text/html", "text/css", "application/javascript", "text/javascript", "application/json", "image/svg+xml", "application/xml", "text/xml")

def sanitize(url):
    s = urlsplit(url); base = os.path.basename(s.path) or "index"
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:50]
    if "." not in base: base += ".bin"
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    name, ext = os.path.splitext(base)
    return f"{name}-{h}{ext}"

def is_text(mime):
    return any(mime.startswith(m) for m in TEXT_MIME)

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    har_path = argv[0]; out = None; page_url = None; as_json = "--json" in argv
    if "--out" in argv: out = argv[argv.index("--out") + 1]
    if "--page-url" in argv: page_url = argv[argv.index("--page-url") + 1]
    if not out: sys.exit("need --out <dir>")
    har = json.load(open(har_path, encoding="utf-8", errors="replace"))
    entries = har.get("log", {}).get("entries", [])
    if not entries: sys.exit("no entries in HAR")
    os.makedirs(out, exist_ok=True)
    # pick the document: explicit --page-url, else HAR's first page, else first text/html 200
    pages = har.get("log", {}).get("pages", [])
    if not page_url and pages: page_url = pages[0].get("title") if pages[0].get("title", "").startswith("http") else None
    doc_entry = None
    for e in entries:
        u = e["request"]["url"]; resp = e.get("response", {}); mime = resp.get("content", {}).get("mimeType", "")
        if page_url and u.split("#")[0] == page_url.split("#")[0] and mime.startswith("text/html"): doc_entry = e; break
    if not doc_entry:
        for e in entries:
            resp = e.get("response", {}); mime = resp.get("content", {}).get("mimeType", "")
            if mime.startswith("text/html") and resp.get("status") in (200, 304) and resp.get("content", {}).get("text"): doc_entry = e; break
    if not doc_entry: sys.exit("no HTML document with a body found in HAR; export the HAR with response bodies enabled")
    doc_url = doc_entry["request"]["url"]; origin = "{0.scheme}://{0.netloc}".format(urlsplit(doc_url))
    # collect resources with bodies
    resources = {}   # url -> {name, mime, text(bool), data}
    for e in entries:
        u = e["request"]["url"]; resp = e.get("response", {}); c = resp.get("content", {})
        body = c.get("text")
        if body is None or u == doc_url: continue
        mime = c.get("mimeType", "application/octet-stream").split(";")[0]
        if c.get("encoding") == "base64":
            try: data = base64.b64decode(body)
            except Exception: continue
            resources[u] = {"name": sanitize(u), "mime": mime, "text": False, "data": data}
        else:
            resources[u] = {"name": sanitize(u), "mime": mime, "text": True, "data": body}
    # build replacement forms for each resource url
    doc_dir = urlsplit(doc_url).path.rsplit("/", 1)[0] + "/"
    def forms(u):
        s = urlsplit(u); out = {u, u.split("#")[0]}
        out.add("//" + s.netloc + s.path + (("?" + s.query) if s.query else ""))
        if s.netloc == urlsplit(doc_url).netloc:
            out.add(s.path + (("?" + s.query) if s.query else "")); out.add(s.path)
            # relative reference as the document most likely wrote it
            if s.path.startswith(doc_dir): out.add(s.path[len(doc_dir):] + (("?" + s.query) if s.query else "")); out.add(s.path[len(doc_dir):])
            out.add(s.path.lstrip("/"))
        out.add(s.path.split("?")[0]); out.add(os.path.basename(s.path))
        return sorted((f for f in out if f and f not in ("/", "")), key=len, reverse=True)
    def rewrite(text, from_url):
        # longest forms first across all resources, so a specific URL wins over a bare basename
        pairs = []
        for u, meta in resources.items():
            for f in forms(u): pairs.append((f, meta["name"]))
        for f, name in sorted(set(pairs), key=lambda x: -len(x[0])):
            if len(f) <= 3: continue   # skip too-short tokens
            text = text.replace(f, name)
        return text
    # write binary + text resources (text rewritten too, for CSS @import/url())
    written = []
    for u, meta in resources.items():
        path = os.path.join(out, meta["name"])
        if meta["text"]:
            open(path, "w", encoding="utf-8", errors="replace").write(rewrite(meta["data"], u) if meta["mime"] in ("text/css", "image/svg+xml") else meta["data"])
        else:
            open(path, "wb").write(meta["data"])
        written.append({"url": u, "file": meta["name"], "mime": meta["mime"], "bytes": len(meta["data"])})
    # write the document, rewritten
    doc = doc_entry["response"]["content"]["text"]
    doc = rewrite(doc, doc_url)
    # neutralise base href so relative rewrites resolve locally
    doc = re.sub(r'<base[^>]*>', '', doc, flags=re.I)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8", errors="replace").write(doc)
    manifest = {"source": har_path, "documentUrl": doc_url, "origin": origin, "resources": len(written),
                "byType": {}, "missingBodies": sum(1 for e in entries if e.get("response", {}).get("content", {}).get("text") is None),
                "index": os.path.join(out, "index.html"), "written": written[:200]}
    for w in written: manifest["byType"][w["mime"]] = manifest["byType"].get(w["mime"], 0) + 1
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    if as_json: print(json.dumps({k: manifest[k] for k in manifest if k != "written"}, indent=1)); return 0
    print(f"document: {doc_url}")
    print(f"wrote {len(written)} resources to {out}/ ({', '.join(f'{v} {k.split('/')[-1]}' for k,v in sorted(manifest['byType'].items(), key=lambda x:-x[1])[:8])})")
    print(f"missing bodies (not in HAR): {manifest['missingBodies']}")
    print(f"\nNow capture it:\n  node capture_page.js {out}/index.html --out ./rfa/site --full-page --viewport 1440x900 --viewport 390x844")
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

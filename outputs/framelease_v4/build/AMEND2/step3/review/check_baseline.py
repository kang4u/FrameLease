"""Compare every file of registered_baseline.json 'files' with the tree (read-only)."""
import hashlib, json, os, sys
ROOT = "/home/kang/Desktop/DAC"
base = json.load(open(os.path.join(ROOT, "outputs/framelease_v4/p1_driver/registered_baseline.json")))
files = base["files"]
bad = []
for rel, sha in sorted(files.items()):
    p = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        got = h.hexdigest()
    except OSError as e:
        got = "MISSING:%s" % e
    if got != sha:
        bad.append((rel, sha, got))
print("baseline files:", len(files), "differing:", len(bad))
for b in bad:
    print("DIFF", *b)
sys.exit(1 if bad else 0)

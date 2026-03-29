import os, json, hashlib, gzip, bz2, lzma, tarfile, io, subprocess
from pathlib import Path
DEBS_DIR, DEP_DIR, METADATA_DIR = Path("debs"), Path("depictions"), Path("metadata")
BASE_URL = "https://iosghost.github.io"
def get_hash(p, a):
    h = hashlib.new(a)
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(8192), b""): h.update(c)
    return h.hexdigest()
def extract_control(dp):
    try:
        with open(dp, "rb") as f:
            if f.read(8) != b"!<arch>\n": return None
            while True:
                h = f.read(60)
                if len(h) < 60: break
                n, s = h[0:16].decode().strip().rstrip('/'), int(h[48:58].decode().strip())
                if n.startswith("control.tar"):
                    c = f.read(s)
                    if n.endswith(".zst"):
                        p = subprocess.Popen(['zstd', '-d', '-c'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                        c, _ = p.communicate(input=c)
                    with tarfile.open(fileobj=io.BytesIO(c)) as tar:
                        for m in tar.getmembers():
                            if m.name.lstrip('./') == "control":
                                raw = tar.extractfile(m).read().decode("utf-8", "ignore")
                                r = {}
                                for l in raw.splitlines():
                                    if ": " in l: k, v = l.split(": ", 1); r[k.strip()] = v.strip()
                                return r
                    break
                else: f.seek(s, 1);
                if s % 2 != 0: f.read(1)
        return None
    except: return None
def rebuild():
    DEBS_DIR.mkdir(exist_ok=True); DEP_DIR.mkdir(exist_ok=True); METADATA_DIR.mkdir(exist_ok=True)
    pkgs, web_data = "", []
    for d in DEBS_DIR.glob("*.deb"):
        c = extract_control(d)
        if not c: continue
        pid = c["Package"]
        mf = METADATA_DIR / f"{pid}.json"
        meta = json.load(open(mf, encoding="utf-8")) if mf.exists() else {}
        entry = {
            "Package": pid, "Name": meta.get("name") or c.get("Name") or pid, "Version": c.get("Version"),
            "Architecture": c.get("Architecture"), "Filename": f"debs/{d.name}", "Size": d.stat().st_size,
            "MD5sum": get_hash(d, "md5"), "SHA1": get_hash(d, "sha1"), "SHA256": get_hash(d, "sha256"),
            "Description": meta.get("description") or c.get("Description"), "Icon": meta.get("icon") or c.get("Icon") or f"{BASE_URL}/CydiaIcon.png"
        }
        for k, v in entry.items(): pkgs += f"{k}: {v}\n"
        pkgs += "\n"
        web_data.append({"id": pid, "name": entry["Name"], "version": entry["Version"], "description": entry["Description"], "icon": entry["Icon"]})
    with open("Packages", "w", encoding="utf-8") as f: f.write(pkgs)
    with open("Packages", "rb") as fi:
        b = fi.read()
        with gzip.open("Packages.gz", "wb") as fo: fo.write(b)
        with bz2.open("Packages.bz2", "wb") as fo: fo.write(b)
        with lzma.open("Packages.xz", "wb") as fo: fo.write(b)
    rel = f"Origin: Ghost\nLabel: Ghost\nMD5Sum:\n {get_hash('Packages','md5')} {os.path.getsize('Packages')} Packages\n"
    with open("Release", "w") as f: f.write(rel)
    with open("repo_data.json", "w", encoding="utf-8") as f: json.dump(web_data, f, ensure_ascii=False, indent=2)
if __name__ == "__main__": rebuild()
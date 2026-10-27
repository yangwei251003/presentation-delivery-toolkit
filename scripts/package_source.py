"""Create and verify a source ZIP without following links or copying local secrets/caches."""
from pathlib import Path
import argparse,hashlib,json,os,zipfile
EXCLUDED={'node_modules','.git','.next','.venv','venv','__pycache__','dist','build'}
def digest(data):return hashlib.sha256(data).hexdigest()
def build(root,out):
    root=root.resolve();out=out.resolve()
    if not root.is_dir() or out.is_relative_to(root):raise ValueError('ZIP must be outside an existing source root')
    if out.exists():raise FileExistsError(out)
    rows=[]
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
        for current,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not(Path(current)/d).is_symlink() and not(Path(current)/d).is_junction())
            for name in sorted(files):
                p=Path(current)/name
                if p.is_symlink() or name.startswith('.env') and not name.endswith('.example') or name.endswith(('.log','.tsbuildinfo')):continue
                rel=p.relative_to(root).as_posix();data=p.read_bytes();z.writestr(rel,data);rows.append({'path':rel,'bytes':len(data),'sha256':digest(data)})
        z.writestr('SOURCE-MANIFEST.json',json.dumps(rows,ensure_ascii=False,indent=2))
    return verify(out)
def verify(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive member')
        rows=json.loads(z.read('SOURCE-MANIFEST.json'))
        if set(names)!={'SOURCE-MANIFEST.json'}|{r['path']for r in rows}:raise ValueError('Unexpected archive member')
        for row in rows:
            rel=Path(row['path'])
            if rel.is_absolute() or '..'in rel.parts or ':'in row['path'] or '\\'in row['path']:raise ValueError('Unsafe archive member')
            data=z.read(row['path'])
            if len(data)!=row['bytes'] or digest(data)!=row['sha256']:raise ValueError('Archive manifest mismatch')
    return {'files':len(rows),'bytes':sum(r['bytes']for r in rows),'crc_and_each_member_sha256':True}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(build(a.source,a.output)))

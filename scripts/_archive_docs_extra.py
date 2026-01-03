import os
import zipfile

SRC = 'docs'
EXCLUDE = {'README.md','ESSENTIALS.md','IMPLEMENTATION_COMPLETE.md'}
ZIP_DEST = os.path.join('docs','archived','2026-01-03_1946_extra.zip')

if not os.path.isdir(SRC):
    print('docs folder not found')
    raise SystemExit(1)

files = [os.path.join(SRC,f) for f in os.listdir(SRC) if f.endswith('.md') and f not in EXCLUDE]
if not files:
    print('No files to archive')
else:
    os.makedirs(os.path.join(SRC,'archived'), exist_ok=True)
    with zipfile.ZipFile(ZIP_DEST,'w',zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, os.path.basename(p))
    for p in files:
        os.remove(p)
    print(f'Archived {len(files)} files to {ZIP_DEST}')

from pathlib import Path
import sys
import importlib
root = Path(__file__).resolve().parents[0]
print('repo root:', root)
for child in root.iterdir():
    src = child / 'src'
    if src.is_dir():
        print('found src:', src)
print('sys.path head 5:', sys.path[:5])
print('find core_kernel:', importlib.util.find_spec('core_kernel'))
print('find core_kernel.contracts:', importlib.util.find_spec('core_kernel.contracts'))

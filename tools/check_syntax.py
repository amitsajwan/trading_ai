import ast
import sys

fpath = 'dashboard/app.py'
with open(fpath, 'r', encoding='utf-8') as f:
    s = f.read()

try:
    ast.parse(s)
    print('PARSE_OK')
except SyntaxError as e:
    print('SyntaxError:', e)
    print('Line:', e.lineno, 'Offset:', e.offset)
    lines = s.splitlines()
    start = max(0, e.lineno - 6)
    end = min(len(lines), e.lineno + 4)
    for i in range(start, end):
        prefix = '>' if (i+1) == e.lineno else ' '
        print(f"{prefix} {i+1}: {lines[i]}")
    sys.exit(1)
except Exception as ex:
    print('Other parse error:', ex)
    sys.exit(2)

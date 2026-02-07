def find_unmatched_try(path='dashboard/app.py'):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    stack = []  # list of (indent, line_no) for try
    for i, raw in enumerate(lines):
        line = raw.rstrip('\n')
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        # detect try:
        if stripped.startswith('try:'):
            stack.append((indent, i+1))
        # detect except or finally
        if stripped.startswith('except') or stripped.startswith('finally'):
            # pop last try at same indentation or less
            if not stack:
                print(f'Unmatched except/finally at line {i+1}: {line}')
            else:
                # find last try with indent <= current
                found = False
                for j in range(len(stack)-1, -1, -1):
                    if stack[j][0] <= indent:
                        stack.pop(j)
                        found = True
                        break
                if not found:
                    print(f'Except at line {i+1} has no matching try at appropriate indent: {line}')
    if stack:
        for indent, ln in stack:
            print(f'Unmatched try starting at line {ln} (indent {indent})')

if __name__ == '__main__':
    find_unmatched_try()

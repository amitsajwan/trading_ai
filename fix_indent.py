with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'r') as f:
    content = f.read()

# Find the _process_tick method and fix indentation
lines = content.split('\n')
in_process_tick = False
for i, line in enumerate(lines):
    if 'def _process_tick' in line:
        in_process_tick = True
        continue
    elif in_process_tick and line.strip().startswith('def ') and '_process_tick' not in line:
        in_process_tick = False
        continue
    elif in_process_tick and line.strip():
        # Fix indentation - should be 8 spaces
        stripped = line.lstrip()
        if stripped and not stripped.startswith(' ') and not stripped.startswith('\"'):
            lines[i] = '        ' + stripped

content = '\n'.join(lines)

with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'w') as f:
    f.write(content)

print('Indentation fixed')
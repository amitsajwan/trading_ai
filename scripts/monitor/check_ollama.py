"""Quick check for Ollama status."""
import httpx
import sys

try:
    r = httpx.get('http://localhost:11434/api/tags', timeout=3)
    if r.status_code == 200:
        models = r.json().get('models', [])
        print(f"[OK] Ollama is running with {len(models)} model(s):")
        for m in models:
            print(f"  - {m['name']}")
        sys.exit(0)
    else:
        print(f"[FAIL] Ollama returned status {r.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Ollama not accessible: {e}")
    sys.exit(1)



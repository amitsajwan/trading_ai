import os
from pathlib import Path

ROOT = Path('.')

def read_env(path: Path):
    if not path.exists():
        return {}
    result = {}
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            result[k.strip()] = v.strip()
    return result


def test_module_env_files_present():
    root = read_env(ROOT / '.env')
    assert root, 'Root .env must exist for tests'

    ui_env = read_env(ROOT / 'dashboard' / 'modular_ui' / '.env')
    assert 'VITE_MARKET_API_URL' in ui_env
    assert 'VITE_WS_URL' in ui_env

    market_env = read_env(ROOT / 'market_data' / '.env')
    assert 'REDIS_HOST' in market_env
    assert 'REDIS_PORT' in market_env

    engine_env = read_env(ROOT / 'engine_module' / '.env')
    assert 'GROQ_API_KEY' in engine_env or 'OPENAI_API_KEY' in engine_env

    news_env = read_env(ROOT / 'news_module' / '.env')
    assert 'GOOGLE_API_KEY' in news_env or 'HUGGINGFACE_API_KEY' in news_env

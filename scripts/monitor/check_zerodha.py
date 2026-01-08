"""Check Zerodha credentials."""
import sys
import os
import json
from pathlib import Path
sys.path.insert(0, os.getcwd())

try:
    from providers.factory import get_provider
    provider = get_provider()

    if provider is None:
        print('ZERODHA_NO_CREDENTIALS')
        sys.exit(1)

    # If provider is a mock, report mock-ok
    if provider.__class__.__name__.lower().startswith('mock'):
        print('ZERODHA_MOCK_OK')
        sys.exit(0)

    # Otherwise try to call profile()
    try:
        profile = provider.profile()
        print('ZERODHA_OK', profile.get('user_id', 'Unknown'))
        sys.exit(0)
    except Exception as e:
        print('ZERODHA_ERROR', str(e)[:50])
        sys.exit(1)
except ImportError:
    print('ZERODHA_MODULE_MISSING')
    sys.exit(1)
except Exception as e:
    print('ZERODHA_ERROR', str(e)[:50])
    sys.exit(1)



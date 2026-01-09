import os
import sys
# Ensure project src is on PYTHONPATH
# Add the package src to sys.path so imports work regardless of how Python was launched
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'market_data', 'src')))

if __name__ == '__main__':
    try:
        from market_data.api_service import app
        import uvicorn
        uvicorn.run(app, host='0.0.0.0', port=8004)
    except Exception as e:
        print('Failed to start market_data API:', e)
        raise

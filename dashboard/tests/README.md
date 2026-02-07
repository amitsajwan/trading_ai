# Dashboard Tests

This directory contains tests for the dashboard module.

## Test Structure

- `test_smoke.py` - Basic smoke tests for API endpoints
- `test_components.py` - UI component tests using Playwright
- `conftest.py` - Pytest configuration and fixtures

## Running Tests

### API Smoke Tests

```bash
# From dashboard directory
cd dashboard
python tests/test_smoke.py
```

### UI Component Tests

First, ensure Playwright browsers are installed:

```bash
# Install Playwright browsers
pip install playwright
playwright install
```

Then run the tests:

```bash
# From dashboard directory
cd dashboard

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_components.py

# Run with browser visible (for debugging)
pytest tests/test_components.py --headed

# Run specific test
pytest tests/test_components.py::test_dashboard_title
```

## Prerequisites

- Dashboard backend running on `http://localhost:8888`
- Dashboard frontend running on `http://localhost:3000`
- Python dependencies: `requests`, `pytest`, `playwright`

## Test Coverage

These tests provide basic validation that:

1. Dashboard API endpoints respond correctly
2. UI components load without errors
3. Basic navigation and display functionality works

For comprehensive testing, consider adding:
- Integration tests with real data
- Performance tests
- Accessibility tests
- Cross-browser compatibility tests
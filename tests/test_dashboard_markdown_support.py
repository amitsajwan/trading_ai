"""Tests for dashboard root HTML including Markdown support scripts."""
from fastapi.testclient import TestClient
from dashboard_pro import app


def test_dashboard_includes_markdown_scripts():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    # Ensure marked (Markdown parser) is included
    assert "marked.min.js" in html
    # Ensure DOMPurify (sanitizer) is included
    assert "dompurify/dist/purify.min.js" in html

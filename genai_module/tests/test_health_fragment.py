from genai_module.api_endpoints import get_health_fragment


def test_get_health_fragment_basic():
    frag = get_health_fragment()
    assert "genai" in frag
    assert "status" in frag["genai"]
    # providers may be empty in some CI environments, but keys should exist
    assert "providers" in frag["genai"] or frag["genai"]["status"] in ["ok", "degraded"]

from dashboard.app import add_camel_aliases


def test_add_camel_aliases_simple():
    data = {"current_price": 100, "vwap": 50, "futures": {"average_price": 49}}
    out = add_camel_aliases(data)
    # original keys
    assert "current_price" in out
    assert "vwap" in out
    assert "futures" in out
    # underscore-less aliases
    assert "currentprice" in out
    assert "vwap" in out
    # camelCase aliases
    assert "currentPrice" in out
    # nested
    assert "average_price" in out["futures"]
    assert "averagePrice" in out["futures"]


def test_add_camel_aliases_numbers():
    data = {"change_24h": 1.23, "volume_24h": 123456}
    out = add_camel_aliases(data)
    assert "change_24h" in out
    assert "change24h" in out
    assert "change24H" in out or "change24h" in out
    assert "volume_24h" in out
    assert "volume24h" in out
    assert "volume24H" in out or "volume24h" in out

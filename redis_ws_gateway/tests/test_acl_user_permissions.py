from redis_ws_gateway.gateway import ClientConnection


def test_user_can_subscribe_engine_channels():
    client = ClientConnection(websocket=None, client_id='c1', role='user')
    assert client.can_subscribe('engine:signal') is True
    assert client.can_subscribe('engine:signal:BANKNIFTY') is True
    assert client.can_subscribe('engine:decision:XYZ') is True
    assert client.can_subscribe('indicators:BANKNIFTY:INDEX') is True


def test_user_cannot_subscribe_admin_only():
    client = ClientConnection(websocket=None, client_id='c2', role='user')
    # internal uses wildcard - still should be allowed for 'internal', but 'user' should not match star for admin-only channels
    assert client.can_subscribe('internal:secret') is False

from core_kernel.contracts import ServiceContainer


def test_service_container_protocol_exists():
    assert hasattr(ServiceContainer, "get")
    assert hasattr(ServiceContainer, "register")
    assert hasattr(ServiceContainer, "reset")


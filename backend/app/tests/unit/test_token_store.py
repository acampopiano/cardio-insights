from app.core.token_store import TokenBlocklist


def test_blocklist_add_and_contains() -> None:
    store = TokenBlocklist()
    assert store.contains("jti-1") is False
    store.add("jti-1")
    assert store.contains("jti-1") is True
    assert store.contains("jti-2") is False


def test_blocklist_is_instance_isolated() -> None:
    a = TokenBlocklist()
    b = TokenBlocklist()
    a.add("shared-looking")
    assert a.contains("shared-looking") is True
    assert b.contains("shared-looking") is False

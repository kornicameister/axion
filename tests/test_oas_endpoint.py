from axion.oas import endpoint


def test_sync_endpoint() -> None:
    @endpoint.oas_endpoint
    def handler() -> None:
        ...

    meta = getattr(handler, '__axion_meta__', None)

    assert meta is not None
    assert meta.operation_id == 'tests.test_oas_endpoint.handler'
    assert meta.asynchronous is False


def test_async_endpoint() -> None:
    @endpoint.oas_endpoint
    async def handler() -> None:
        ...

    meta = getattr(handler, '__axion_meta__', None)

    assert meta is not None
    assert meta.operation_id == 'tests.test_oas_endpoint.handler'
    assert meta.asynchronous is True

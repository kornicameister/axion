import pytest


@pytest.mark.mypy_testing
def handler_not_in_oas() -> None:
    from axion import oas_endpoint
    from axion import response

    @oas_endpoint
    async def not_oas_handler(  # E: not_oas_handler is not OAS operation  [axion-no-op]
    ) -> response.Response:
        return {
            'http_code': 200,
        }

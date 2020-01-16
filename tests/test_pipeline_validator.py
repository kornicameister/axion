import pytest_mock as ptm

from axion import fp
from axion.pipeline import validator


class TestHttpCode:
    def test_always_true_default_repr(
            self,
            mocker: ptm.MockFixture,
    ) -> None:

        oas_op = mocker.stub()
        oas_op.id = mocker.ANY
        oas_op.responses = {
            'default': mocker.ANY,
        }

        v = validator.HttpCodeValidator(oas_op)

        for http_code in range(200, 500):
            assert fp.Result.is_ok(v({'http_code': http_code}))

    def test_true_if_code_matches(
            self,
            mocker: ptm.MockFixture,
    ) -> None:
        oas_op = mocker.stub()
        oas_op.id = mocker.ANY
        oas_op.responses = responses = {
            http_code: mocker.ANY for http_code in range(200, 500)
        }

        v = validator.HttpCodeValidator(oas_op)

        for http_code in responses.keys():
            assert fp.Result.is_ok(v({'http_code': http_code}))

    def test_fail_if_no_match(
            self,
            mocker: ptm.MockFixture,
    ) -> None:
        oas_op = mocker.stub()
        oas_op.id = op_id = mocker.ANY
        oas_op.responses = responses = {
            http_code: mocker.ANY for http_code in range(200, 204)
        }

        v = validator.HttpCodeValidator(oas_op)
        wrong_code = 304

        result = v({'http_code': wrong_code})

        assert not fp.Result.is_ok(result)
        assert fp.Result.is_fail(result)

        assert result.error.oas_operation_id == mocker.ANY
        assert result.error.occurred_at == 'return.http_code'
        assert result.error.message == (
            f'HTTP code {wrong_code} does not match {op_id} '
            f'response codes {{{", ".join(map(str, responses.keys()))}}}.'
        )

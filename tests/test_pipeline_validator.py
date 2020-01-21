import pytest
import pytest_mock as ptm

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
            assert v({'http_code': http_code}) == http_code

    def test_true_if_code_matches(
            self,
            mocker: ptm.MockFixture,
    ) -> None:
        oas_op = mocker.stub()
        oas_op.id = mocker.ANY
        oas_op.responses = responses = {
            http_code: mocker.ANY
            for http_code in range(200, 500)
        }

        v = validator.HttpCodeValidator(oas_op)

        for http_code in responses.keys():
            assert v({'http_code': http_code}) == http_code

    def test_fail_if_no_match(
            self,
            mocker: ptm.MockFixture,
    ) -> None:
        oas_op = mocker.stub()
        oas_op.id = op_id = mocker.ANY
        oas_op.responses = responses = {
            http_code: mocker.ANY
            for http_code in range(200, 204)
        }

        v = validator.HttpCodeValidator(oas_op)
        wrong_code = 304

        with pytest.raises(validator.ValidationError) as err:
            v({'http_code': wrong_code})

        assert err.value.oas_operation_id == mocker.ANY
        assert err.value.occurred_at == 'return.http_code'
        assert err.value.message == (
            f'HTTP code {wrong_code} does not match {op_id} '
            f'response codes {{{", ".join(map(str, responses.keys()))}}}.'
        )

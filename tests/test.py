from json import dumps
from uuid import uuid4

import pytest
from sanic import Request
from sanic_testing.testing import TestingResponse

from service import app
from service.blue_print import SaleRequestInput, RefundRequestInput
from service.business.functions import CreditCardDataDataclass
from service.business.params import HeartlandParams, Constants
from service.json_util import EnhancedJSONEncoder

CREDIT_CARD_DATA = CreditCardDataDataclass(
    number="None", exp_month="None", exp_year="None", cvn="None",
)

HEARTLAND_PARAMS = HeartlandParams(
    url="https://cert.api2.heartlandportico.com",
    public_key="None",
    private_key="None",
    term_id="None",
    cert_str="None",
    account_num="None",
    developer_id="None",
    version_number="None",
    username="None",
    password="None",
    constants=Constants(default_currency="USD"),
)


@pytest.fixture(scope="session")
def testing_app():
    app.ctx.echo = True
    return app


SanicTuple = tuple[Request, TestingResponse]


@pytest.mark.asyncio
async def test_app_home_route(testing_app):
    sanic: SanicTuple = await testing_app.asgi_client.get("/")
    assert sanic[1].status_code == 404


@pytest.mark.asyncio
async def test_sale(testing_app):
    request_body: str = dumps(SaleRequestInput(
        amount=float("3.33"),
        credit_card_data=CREDIT_CARD_DATA,
        params=HEARTLAND_PARAMS,
        reference=uuid4(),
        qa=True,
    ), cls=EnhancedJSONEncoder)

    sanic: SanicTuple = await testing_app.asgi_client.post(
        "/api/heartland/sale",
        content=request_body.encode("utf-8")
    )
    assert sanic[1].status_code == 200


@pytest.mark.asyncio
async def test_authorize(testing_app):
    request_body: str = dumps(SaleRequestInput(
        amount=float("3.33"),
        credit_card_data=CREDIT_CARD_DATA,
        params=HEARTLAND_PARAMS,
        reference=uuid4(),
        qa=True,
    ), cls=EnhancedJSONEncoder)

    sanic: SanicTuple = await testing_app.asgi_client.post(
        "/api/heartland/authorize",
        content=request_body.encode("utf-8")
    )
    assert sanic[1].status_code == 200


@pytest.mark.asyncio
async def test_settle(testing_app):
    request_body: str = dumps(SaleRequestInput(
        amount=float("3.33"),
        credit_card_data=CREDIT_CARD_DATA,
        params=HEARTLAND_PARAMS,
        reference=uuid4(),
        qa=True,
    ), cls=EnhancedJSONEncoder)

    sanic: SanicTuple = await testing_app.asgi_client.post(
        "/api/heartland/settle",
        content=request_body.encode("utf-8")
    )
    assert sanic[1].status_code == 200


@pytest.mark.asyncio
async def test_refund(testing_app):
    request_body: str = dumps(RefundRequestInput(
        amount=float("3.33"),
        # credit_card_data=CREDIT_CARD_DATA,
        params=HEARTLAND_PARAMS,
        heartland_transaction_id="None",
        payment_transaction_amount="None",
        reference=uuid4(),
        qa=True,
    ), cls=EnhancedJSONEncoder)

    sanic: SanicTuple = await testing_app.asgi_client.post(
        "/api/heartland/refund",
        content=request_body.encode("utf-8")
    )
    assert sanic[1].status_code == 200

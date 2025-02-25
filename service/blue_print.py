from contextlib import suppress
from dataclasses import dataclass
from json import dumps
from typing import cast, Union
from uuid import UUID

from sanic import json, Request
from sanic.blueprints import Blueprint

from service.business.functions import OnlinePayments, card_data, CreditCardDataDataclass
from service.business.params import HeartlandParams
from service.json_util import ignore_properties, EnhancedJSONEncoder

bp = Blueprint("Heartland", url_prefix="/api/heartland")


@dataclass
class RequestInput:
    params: HeartlandParams
    reference: UUID
    qa: bool

    def __post_init__(self):
        if not isinstance(self.params, HeartlandParams):
            self.params = ignore_properties(HeartlandParams, self.params)
        if self.reference and not isinstance(self.reference, UUID):
            with suppress(ValueError):
                self.reference = UUID(cast(str, self.reference))


@dataclass
class SaleRequestInput(RequestInput):
    amount: float
    zip_code: Union[str, None]
    credit_card_data: CreditCardDataDataclass

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.credit_card_data, CreditCardDataDataclass):
            self.credit_card_data = \
                ignore_properties(CreditCardDataDataclass, self.credit_card_data)


@dataclass
class RefundRequestInput(RequestInput):
    heartland_transaction_id: str
    payment_transaction_amount: str
    amount: float | None = None


@dataclass
class CaptureRequestInput(RequestInput):
    heartland_transaction_id: str
    payment_transaction_amount: str


@bp.post("/sale")
def sale(request: Request):
    request_input = ignore_properties(SaleRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).sale(
        amount=request_input.amount,
        card=card_data(
            number=request_input.credit_card_data.number,
            exp_month=request_input.credit_card_data.exp_month,
            exp_year=request_input.credit_card_data.exp_year,
            cvn=request_input.credit_card_data.cvn,
        ),
        zip_code=request_input.zip_code
    )
    return json(result)


@bp.post("/authorize")
def authorize(request):
    request_input = ignore_properties(SaleRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).authorize(
        amount=request_input.amount,
        card=card_data(
            number=request_input.credit_card_data.number,
            exp_month=request_input.credit_card_data.exp_month,
            exp_year=request_input.credit_card_data.exp_year,
            cvn=request_input.credit_card_data.cvn,
        ),
        zip_code=request_input.zip_code
    )
    return json(result)


@bp.post("/settle")
def settle(request):
    request_input = ignore_properties(RequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).settle()
    return json({"settle_status": True})


@bp.post("/capture")
def capture(request):
    request_input = ignore_properties(CaptureRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).capture(
        heartland_transaction_id=request_input.heartland_transaction_id,
        payment_transaction_amount=request_input.payment_transaction_amount,
    )
    return json({"settle_status": True})


@bp.post("/refund")
def refund(request):
    request_input = ignore_properties(RefundRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).refund(
        heartland_transaction_id=request_input.heartland_transaction_id,
        payment_transaction_amount=request_input.payment_transaction_amount,
        amount=request_input.amount,
    )
    return json(result)


@bp.post("/reversal")
async def reversal(request):
    request_input = ignore_properties(RefundRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).reversal(
        heartland_transaction_id=request_input.heartland_transaction_id,
        payment_transaction_amount=request_input.payment_transaction_amount,
    )
    return json(result)


@bp.post("/void")
async def void(request):
    request_input = ignore_properties(RefundRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).void(
        heartland_transaction_id=request_input.heartland_transaction_id,
        payment_transaction_amount=request_input.payment_transaction_amount,
    )
    return json(result)


@bp.post("/force/refund")
async def force_refund(request):
    request_input = ignore_properties(RefundRequestInput, request.json)
    if getattr(request.app.ctx, "echo", False):
        return json(dumps(request_input, cls=EnhancedJSONEncoder))

    result = OnlinePayments(
        params=request_input.params,
        reference=request_input.reference,
        qa=request_input.qa
    ).force_refund(
        heartland_transaction_id=request_input.heartland_transaction_id,
        payment_transaction_amount=request_input.payment_transaction_amount,
        amount=request_input.amount,
    )
    return json(result)

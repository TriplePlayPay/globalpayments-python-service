from dataclasses import dataclass
from typing import Any, Union
from uuid import UUID

from python_sdk.globalpayments.api import ServicesConfig, ServicesContainer
from python_sdk.globalpayments.api.entities import Transaction
from python_sdk.globalpayments.api.entities.address import Address
from python_sdk.globalpayments.api.payment_methods.credit import CreditCardData
from python_sdk.globalpayments.api.services.batch_service import BatchService

from service.business.params import HeartlandParams
from service.packages.lumberjack import get_logger

logger = get_logger()


@dataclass
class CreditCardDataDataclass:
    number: str
    exp_month: str
    exp_year: str
    cvn: Union[str, None] = None


def card_data(
    number: str, exp_month: str, exp_year: str, cvn: Union[str, None]
) -> CreditCardData:
    card = CreditCardData()
    card.number = number
    card.exp_month = exp_month
    card.exp_year = f"20{exp_year}"
    if cvn:
        card.cvn = cvn
    return card


@dataclass
class AddressDataclass:
    street: str
    zipcode: str


def address_data(street: str, zipcode: str) -> Address:
    address = Address()
    address.street_address_1 = street
    address.postal_code = zipcode
    return address


# noinspection PyMethodMayBeStatic
class OnlinePayments:
    """
    This encapsulates some data to assist in communications
    with the HeartlandAPI.
    """

    def __init__(self, params: HeartlandParams, reference: UUID, qa=False):
        self.params = params
        self.reference = reference
        config = ServicesConfig()
        config.secret_api_key = params.private_key
        config.developer_id = params.developer_id
        config.service_url = params.url
        ServicesContainer.configure(config)

    def __results(self, transaction) -> dict[str, Any]:
        fields = {}
        for key in dir(transaction):
            value = getattr(transaction, key)
            if not key.startswith("_") and isinstance(value, str):
                fields[key] = value
        return fields

    def sale(self, amount: float, card: CreditCardData):
        if card.cvn:
            transaction = (
                card.charge(amount)
                .with_cvc(card.cvn)
                # .with_address(address)
                .with_currency(self.params.constants.default_currency)
                .with_client_transaction_id(self.reference)
                .execute()
            )
        else:
            transaction = (
                card.charge(amount)
                .with_currency(self.params.constants.default_currency)
                .with_client_transaction_id(self.reference)
                .execute()
            )
        return self.__results(transaction)

    def verify(self, card: CreditCardData, address: Address):
        transaction = (
            card.verify()
            .with_address(address)
            .with_client_transaction_id(self.reference)
            .execute()
        )
        return self.__results(transaction)

    def authorize(self, amount: float, card: CreditCardData):
        if card.cvn:
            transaction = (
                card.authorize(amount)
                .with_cvc(card.cvn)
                .with_currency(self.params.constants.default_currency)
                .with_client_transaction_id(self.reference)
                .execute()
            )
        else:
            transaction = (
                card.authorize(amount)
                .with_currency(self.params.constants.default_currency)
                .with_client_transaction_id(self.reference)
                .execute()
            )

        return self.__results(transaction)

    def settle(self):
        result = BatchService.close_batch()
        logger.info(f"Result from closing the batch: {result}")
        return result

    def refund(
        self,
        heartland_transaction_id: str,
        payment_transaction_amount: str,
        amount: Union[float, None]
    ):
        transaction = Transaction.from_id(heartland_transaction_id)

        if amount is not None and float(payment_transaction_amount) != amount:
            result = (
                transaction.refund(amount)
                .with_currency(self.params.constants.default_currency)
                .execute()
            )
        else:
            try:
                result = transaction.void().execute()
            except Exception:
                logger.exception(
                    "Exception running void, the batch probably already closed"
                )
                result = (
                    transaction.refund(float(payment_transaction_amount))
                    .with_currency(self.params.constants.default_currency)
                    .execute()
                )

        return self.__results(result)

    def force_refund(
        self,
        heartland_transaction_id: str,
        payment_transaction_amount: str,
        amount: Union[float, None]
    ):
        transaction = Transaction.from_id(heartland_transaction_id)
        result = (
            transaction.refund(float(payment_transaction_amount))
            .with_currency(self.params.constants.default_currency)
            .execute()
        )
        return self.__results(result)

    def reversal(
        self,
        heartland_transaction_id: str,
        payment_transaction_amount: str
    ):
        transaction = Transaction.from_id(heartland_transaction_id)
        result = (
            transaction.reverse(float(payment_transaction_amount))
            .with_currency(self.params.constants.default_currency)
            .execute()
        )
        return self.__results(result)

    def void(
        self,
        heartland_transaction_id: str,
        payment_transaction_amount: str
    ):
        transaction = Transaction.from_id(heartland_transaction_id)
        result = (
            transaction.void()
            .with_currency(self.params.constants.default_currency)
            .execute()
        )
        return self.__results(result)

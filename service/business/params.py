from dataclasses import dataclass

from service.json_util import ignore_properties


@dataclass
class Constants:
    default_currency: str


@dataclass
class HeartlandParams:
    url: str
    public_key: str
    private_key: str
    term_id: str
    cert_str: str
    account_num: str
    developer_id: str
    version_number: str
    username: str
    password: str
    constants: Constants

    def __post_init__(self):
        self.constants = ignore_properties(Constants, self.constants)

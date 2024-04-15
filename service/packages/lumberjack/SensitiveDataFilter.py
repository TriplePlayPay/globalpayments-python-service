import re
import logging
from logging import LogRecord


class SensitiveDataFilter(logging.Filter):
    """
    This is a class dedicated to removing sensitive information from logs.
    """

    FILTERS = [
        r"\b\d{3}\b",  # CVV
        r"\b\d{4}\b",  # CVV
        r"\b\d{16}\b",  # credit card
        r"\b\d{15}\b",  # credit card
        r"\b\d{9}\b",  # SSN
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",  # credit card
        r"\d{4}-\d{4}-\d{4}-\d{4}",  # credit card
        r"\b\d{4} \d{4} \d{4} \d{4}\b",  # credit card
        r"\d{4} \d{4} \d{4} \d{4}",  # credit card
        r"\b\d{4}\d{4}\d{4}\d{4}\b",  # credit card
        r"\d{4}\d{4}\d{4}\d{4}",  # credit card
        r"\b^3[47][0-9]{13}$\b",  # AMEX
        r"\b^4[0-9]{12}(?:[0-9]{3})?$\b",  # VISA
        r"\b^5[1-5][0-9]{14}$\b",  # MC
        r"\b^6(?:011|5[0-9]{2})[0-9]{12}$\b",  # Discover
        r"\b^(?:5[0678]\d\d|6304|6390|67\d\d)\d{8,15}$\b",  # maestro card
    ]

    def filter(self, record: LogRecord) -> bool:
        """
        Modify the log record to mask sensitive data

        Args:
            record: LogRecord

        Returns:
            bool
        """
        record.msg = self.mask_sensitive_data(record.msg)
        return True

    def mask_sensitive_data(self, message: str) -> str:
        """
        Implementation of logic to mask or modify sensitive data.

        Args:
            message: str

        Returns:
            str
        """
        r = str(message)
        for a_filter in self.FILTERS:
            result = self.replace_if_pattern_exists_in_message(a_filter, str(r))
            if result:
                r = result

        return r

    @staticmethod
    def replace_if_pattern_exists_in_message(pattern: str, message: str) -> str | None:
        """
        Determines if a given message contains a regular expression pattern.

        Args:
            pattern: str
            message: str

        Returns:
            str | None
        """
        compiled_pattern = re.compile(pattern)
        if bool(re.search(compiled_pattern, message)):
            return compiled_pattern.sub("[REDACTED]", message)
        else:
            return None

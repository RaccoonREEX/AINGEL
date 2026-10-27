"""Remove API query strings from local request access logs."""

import logging
import re


class RedactAPIQuery(logging.Filter):
    def filter(self, record):
        # Render before redacting, because Daphne logs a mapping of request fields.
        message = record.getMessage()
        record.msg = re.sub(r"(/api/[^\s?\"']*)\?[^\s\"']*", r"\1?[redacted]", message)
        record.args = ()
        return True

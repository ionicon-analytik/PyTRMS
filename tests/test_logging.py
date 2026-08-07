import logging

import pytrms


def test_urllib3_default_log_level():
    assert logging.getLogger("urllib3").getEffectiveLevel() >= logging.WARNING

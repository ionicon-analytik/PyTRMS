import logging

import pytrms


def test_urllib3_default_log_level():
    assert logging.getLogger("urllib3").getEffectiveLevel() >= logging.WARNING


def test_enable_extended_logging_sets_urllib3_debug():
    urllib3_log = logging.getLogger("urllib3")
    prev_level = urllib3_log.level
    prev_propagate = urllib3_log.propagate
    try:
        pytrms.enable_extended_logging(logging.DEBUG)
        assert urllib3_log.getEffectiveLevel() == logging.DEBUG
        assert urllib3_log.propagate is True
    finally:
        urllib3_log.setLevel(prev_level)
        urllib3_log.propagate = prev_propagate

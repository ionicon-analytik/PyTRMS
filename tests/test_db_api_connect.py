import time
from unittest.mock import MagicMock

import pytest
import requests
import requests.adapters

from pytrms.clients.db_api import IoniConnect
from pytrms._base import _IoniConnectBase
from requests.exceptions import ConnectionError


@pytest.fixture
def ioni_connect():
    c = IoniConnect.__new__(IoniConnect)
    _IoniConnectBase.__init__(c, "127.0.0.1", 5066)
    c.url = "http://127.0.0.1:5066"
    c._http_adapter = requests.adapters.HTTPAdapter(max_retries=IoniConnect._retry_policy)
    c.session = requests.Session()
    c.session.mount("http://", c._http_adapter)
    return c


def test_connect_uses_short_ping_timeouts(ioni_connect):
    timeouts = []

    def fail_get(url, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        raise ConnectionError()

    ioni_connect.session.get = fail_get

    with pytest.raises(TimeoutError):
        ioni_connect.connect(timeout_s=0.55)

    assert timeouts
    assert all(t == (0.5, 3.0) for t in timeouts)
    assert ioni_connect.session is None


def test_connect_returns_after_ping_succeeds(ioni_connect):
    calls = {"n": 0}

    def flaky_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError()
        ok = MagicMock()
        ok.raise_for_status = MagicMock()
        return ok

    ioni_connect.session.get = flaky_get
    started = time.monotonic()
    ioni_connect.connect(timeout_s=10)
    assert time.monotonic() - started < 2.0
    assert ioni_connect.session is not None

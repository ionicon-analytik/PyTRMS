"""
@file conftest.py

"""
import re
import pytest

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import (
    HttpWaitStrategy,
    LogMessageWaitStrategy
)

TAG = None  # "158138a"

IMAGE = "git.ionicon.local/ionisoft/db-api" + (":" + TAG if TAG else "")


start_hint = re.compile(r"in Program\.cs_Main@([0-9]+): starting web api...")


@pytest.fixture(scope="function")#module")
def api_container():
    with DockerContainer(IMAGE).with_exposed_ports(5066) as container:
        port = container.get_exposed_port(5066)
        container.waiting_for(LogMessageWaitStrategy(start_hint))
        container.waiting_for(HttpWaitStrategy(port, "/api/ping"))

        yield port


@pytest.fixture
def API(api_container):
    from pytrms.clients import db_api

    return db_api.IoniConnect(port=api_container)


def pytest_collection_modifyitems(config, items):
    """
    This automatically adds a marker `@pytest.mark.apitest`
    to everything requiring an `api_container`.
    """
    for item in items:
        if "api_container" in getattr(item, "fixturenames", []):
            item.add_marker("apitest")



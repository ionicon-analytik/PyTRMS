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

image = "git.ionicon.local/ionisoft/db-api:158138a"

start_hint = re.compile(r"in Program\.cs_Main@([0-9]+): starting web api...")


@pytest.fixture(scope="module")
def api_container():
    with DockerContainer(image).with_exposed_ports(5066) as container:
        port = container.get_exposed_port(5066)        
        container.waiting_for(LogMessageWaitStrategy(start_hint))
        container.waiting_for(HttpWaitStrategy(port, "/api/ping"))

        yield port


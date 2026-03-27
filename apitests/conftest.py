"""
@file conftest.py

"""
import re
import pytest

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import (
    LogMessageWaitStrategy,
    HttpWaitStrategy,
)

import platform
if platform.uname().system == "Linux":
    # set up rootless docker:
    os = platform.os
    os.environ["DOCKER_HOST"] = "unix:///run/user/%d/docker.sock" % os.getuid()


def make_container(image = "git.ionicon.local/ionisoft/db-api", tag = "latest"):
    # this is used to wait for Db-API to respond..
    start_hint = re.compile(r"in Program\.cs_Main@([0-9]+): starting web api...")
    start_verify = "/api/ping"
    api_port = 5066  # inside the container, don't change!
    return (
        DockerContainer(image + ":" + tag)
        .with_exposed_ports(api_port)
        .waiting_for(LogMessageWaitStrategy(start_hint))
        .waiting_for(HttpWaitStrategy(api_port, start_verify))
    )


# =========== pytest.fixtures ===================================================== #

@pytest.fixture(scope="module")
def api_container(request):
    if request.config.getoption("--attach-running"):
        yield 5066

    else:
        with make_container() as conti:
            yield conti.get_exposed_port(5066)


@pytest.fixture
def API(api_container):
    from pytrms.clients import db_api

    attach_running = (api_container == 5066)  # fixture resolves to exposed port

    DB_API = db_api.IoniConnect(port=api_container)

    help_msg = (
        "no connection to container! try 'poetry run python apitests/conftests.py' to fire up the container and diagnose the issue."
        if attach_running else
        "no connection to api! attempt to connect to localhost:5066 failed. make sure an instance is running locally and try again."
    )
    assert DB_API.is_connected, help_msg

    return DB_API


# =========== pytest.configure ==================================================== #

def pytest_addoption(parser):
    parser.addoption("--attach-running", action="store_true",
        help="assume the API is running on port 5066 and attach, instead of using a container")

def pytest_collection_modifyitems(config, items):
    """
    This automatically adds a marker `@pytest.mark.apitest`
    to everything requiring an `api_container`.
    """
    for item in items:
        if "api_container" in getattr(item, "fixturenames", []):
            item.add_marker("apitest")


if __name__ == '__main__':
    import sys
    import requests

    args = iter(sys.argv)
    US = next(args)
    TAG = next(args, "latest")

    IMAGE = "git.ionicon.local/ionisoft/db-api"

    with make_container(IMAGE, TAG) as conti:
        print(US, "...OK")
        print("docker container running")
        PORT = conti.get_exposed_port(5066)
        # the API should be up and running at this point!
        print("requesting /api/ping...")
        r = requests.get(f"http://localhost:{PORT}/api/ping")
        r.raise_for_status()
        print(r.text)
        print("Image:", IMAGE)
        print("Tag:", TAG)
        print("Port:", PORT)
        print()
        input("press Enter to shut down...")


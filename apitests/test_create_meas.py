"""
Test of modules
- pytrms.clients.db_api
- pytrms.measurement

"""
import json
import threading
import contextlib
import logging

import pytest

import pytrms.measurement as MEAS

log = logging.getLogger(__name__)


@contextlib.contextmanager
def mock_componist(api, url_expected):

    def x():
        log.warning("mocking out the AME system protocol!")
        e = next(api.iter_events())
        # asserts won't work in a background thread!
        if e.event != "new measurement": log.error(e.event)
        if e.data  != url_expected:      log.error(e.data)
        # now, follow the protocol: this will trigger the event: 'start measurement':
        rv = api.patch(e.data, { "isRunning": True })

    t = threading.Thread(target=x) #mock_componist) #, args=(url_expected,))
    try:
        t.start()
        yield
    finally:
        t.join()


@pytest.mark.dependency()
def test_db_empty(API):
    assert API.get("/api/recipes/1") is None, "database not empty"


@pytest.mark.dependency(depends=["test_db_empty"])
def test_create_recipe(API):

    API.post("/api/recipes", {"name": "uno"})

    j = API.get("/api/recipes")
    assert j["count"] == 1

    j = API.get("/api/recipes/1")
    assert j["path"] == "/ame/AME/Recipes/uno"

    ## per default, there *must* be a Composition for this to be a "recipe":
    assert API.get("/api/recipes/1/files/meta?name=Composition") is not None


@pytest.mark.dependency(depends=["test_create_recipe"])
def test_recipe_file_api(API):

    j = API.get("/api/recipes/1/files/meta?name=Composition")
    assert "entry" in j
    assert j["entry"]["name"] == "Composition"
    assert j["entry"]["path"] == "/Composition"
    assert j["entry"]["type"] == "file"
    assert j["entry"]["size"] > 0
    assert j["entry"]["etag"].startswith("W/\"")

    body = API.get("/api/recipes/1/files/content?name=Composition")
    assert len(body) == j["entry"]["size"]

    content = body.decode()
    assert len(content) > 0


@pytest.mark.dependency(depends=["test_create_recipe"])
def test_create_measurement(API):

    assert API.get("/api/measurements/last") is None

    r = API.post("/api/measurements", { "recipeDirectory": "/ame/AME/Recipes/uno" })
    j = API.get(r.href)

    assert j["recipeDirectory"] == "/ame/AME/Recipes/uno"

    j = API.get("/api/measurements/last")
    assert j["_links"]["self"]["href"] == "/api/measurements/1"

    ## not yet started
    assert API.get("/api/measurements/current") is None


@pytest.mark.dependency(depends=["test_create_measurement"])
def test_measurement_class_implements_protocol(API):

    SUT = MEAS.PreparingMeasurement(API)

    # ------- start -----------------------------------------------------------
    assert not SUT.is_running
    assert not SUT.url
    assert not len(SUT.filenames)

    with mock_componist(API, url_expected="/api/measurements/2"):
        SUT.start("/ame/AME/Recipes/uno")  # will wait for 'start measurement'

    assert SUT.is_running
    assert SUT.url == API.get_location("/api/measurements/current")

    ## ------ sourcefiles ------------------------------------------------------

    assert len(SUT.filenames) == 0

    SUT.add_sourcefile("/ame/AMEData/foo/zoom.h5")
    SUT.add_sourcefile("/ame/AMEData/bar/zoom.h5")

    assert len(SUT.filenames) == 2

    ## ------ stop -------------------------------------------------------------

    SUT.stop()

    assert not SUT.is_running
    assert SUT.url == "/api/measurements/2"
    assert API.get("/api/measurements/current") is None


@pytest.mark.dependency(depends=["test_measurement_class_implements_protocol"])
def test_measurement_post_process(API):

    SUT = MEAS.Measurement(API, id=2)

    assert len(SUT.filenames) == 2

    assert SUT.filenames[0] == "/ame/AMEData/foo/zoom.h5"
    assert SUT.filenames[1] == "/ame/AMEData/bar/zoom.h5"


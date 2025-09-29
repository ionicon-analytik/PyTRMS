"""
Test of module pytrms.clients.db_api

"""
import pytest


@pytest.fixture
def API(api_container):
    from pytrms.clients import db_api

    return db_api.IoniConnect(port=api_container)


"""
[
  {
    "border_peak": {
      "name": "m015_o",
      "center": 15,
      "ion": "",
      "ionic_isotope": "",
      "parent": "",
      "isotopic_abundance": 0,
      "k_rate": 2,
      "multiplier": 1,
      "resolution": 0
    },
    "low": 14.971399999999999153,
    "high": 15.057800000000000296,
    "peak": [],
    "mode": 1,
    "shift": 0
  },
"""

@pytest.fixture
def PEAK_TABLE():
    from io import StringIO
    import json
    from pytrms import peaktable

    s = StringIO(json.dumps([
      {
        "border_peak": {
          "name": "m015_o",
          "center": 15,
          "ion": "",
          "ionic_isotope": "",
          "parent": "",
          "isotopic_abundance": 0,
          "k_rate": 2,
          "multiplier": 1,
          "resolution": 0
        },
        "low": 14.5,
        "high": 15.5,
        "peak": [
          {
            "name": "m015_fitted",
            "center": 15.1234,
            "ion": "",
            "ionic_isotope": "",
            "parent": "",
            "isotopic_abundance": 0,
            "k_rate": 2,
            "multiplier": 1,
            "resolution": 0
          },
        ],
        "mode": 2,
        "shift": 0
      },
    ]))
    return peaktable.PeakTable._parse_ionipt(s)


@pytest.mark.apitest
def test_status(API):
    r = API.get("/api/status")
    assert r["_links"]["self"]["href"] == "/api/status"


@pytest.mark.apitest
def test_sync(API, PEAK_TABLE):

    r = API.sync(PEAK_TABLE)
    j = API.get("/api/peaks")

    assert j["count"] == 2

    PEAKS = j["_embedded"]["peaks"]

    assert len(PEAKS) == 2

    assert PEAKS[1]["_links"]["parent"] == { "href": "/api/peaks/1" }
    assert "child" not in PEAKS[1]["_links"].keys()



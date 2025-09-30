"""
Test of module pytrms.peaktable

"""
import pytest

from pytrms import peaktable


@pytest.fixture
def PT():
    """
    this creates a dummy peaktable with 2 nominal peaks and 1 fitpeak:

    - m_42
      |_ fit_42.1234
    - m_57

    (3 peaks total)
    """
    pt = peaktable.PeakTable([
        peaktable.Peak(42),
        peaktable.Peak(57),
    ])
    pt.peaks.append(peaktable.Peak(42.1234, parent=pt.peaks[0]))

    assert len(pt) == 3, "peaktable definition out of date"
    assert len(pt.nominal) == 2
    assert len(pt.fitted) == 1

    return pt


def test_sync_updates_sparingly(API, PT):
    r = API.sync(PT)
    assert 3 == r["added"]
    assert 0 == r["updated"]
    assert 0 == r["up-to-date"]

    r = API.sync(PT)
    assert 0 == r["added"]
    assert 0 == r["updated"]
    assert 3 == r["up-to-date"]

    PT.peaks[0].shift = -0.234
    PT.peaks[1].resolution = 3456
    r = API.sync(PT)
    assert 0 == r["added"]
    assert 2 == r["updated"]
    assert 1 == r["up-to-date"]

    PT.peaks.append(peaktable.Peak(23.0))
    r = API.sync(PT)
    assert 1 == r["added"]
    assert 0 == r["updated"]
    assert 3 == r["up-to-date"]

    j = API.get("/api/peaks")
    PEAKS = j["_embedded"]["peaks"]

    assert j["count"] == 4
    assert len(PEAKS) == 4

    ## sorted by id (insertion order) ??
    assert PEAKS[0]["center"] == 42.0
    assert PEAKS[1]["center"] == 42.1234
    assert PEAKS[2]["center"] == 57.0
    assert PEAKS[3]["center"] == 23.0


def test_sync_links_children_to_parent(API, PT):
    r = API.sync(PT)
    assert 3 == r["added"]
    assert 0 == r["updated"]
    assert 0 == r["up-to-date"]
    assert 1 == r["linked"]
    assert 0 == r["unlinked"]

    j = API.get("/api/peaks?only=parents")
    assert j["count"] == 1

    j = API.get("/api/peaks?only=children")
    assert j["count"] == 1

    j = API.get("/api/peaks")
    PEAKS = j["_embedded"]["peaks"]

    assert j["count"] == 3
    assert len(PEAKS) == 3

    ## sorted by id (insertion order) ??
    assert PEAKS[0]["center"] == 42.0
    assert PEAKS[1]["center"] == 42.1234
    assert PEAKS[2]["center"] == 57.0

    ## only the fit-peak has a parent ?
    assert "parent" not in PEAKS[0]["_links"].keys()
    assert "parent"     in PEAKS[1]["_links"].keys()
    assert "parent" not in PEAKS[2]["_links"].keys()

    # is mass 42.1234 linked to nominal mass 42 ?
    assert PEAKS[0]["_links"]["self"] == { "href": "/api/peaks/1" }
    assert PEAKS[1]["_links"]["parent"] == { "href": "/api/peaks/1" }


def test_sync_unlinks_children(API, PT):

    PT.peaks.append(peaktable.Peak(42.3456, parent=PT.peaks[0]))
    PT.peaks.append(peaktable.Peak(57.0815, parent=PT.peaks[1]))

    r = API.sync(PT)
    assert 5 == r["added"]
    assert 0 == r["updated"]
    assert 0 == r["up-to-date"]
    assert 3 == r["linked"]
    assert 0 == r["unlinked"]

    j = API.get("/api/peaks?only=parents")
    assert j["count"] == 2

    j = API.get("/api/peaks?only=children")
    assert j["count"] == 3

    j = API.get("/api/peaks")
    PEAKS = j["_embedded"]["peaks"]

    assert PEAKS[0]["center"] == 42.0
    assert PEAKS[1]["center"] == 42.1234
    assert PEAKS[2]["center"] == 42.3456
    assert PEAKS[3]["center"] == 57.0
    assert PEAKS[4]["center"] == 57.0815

    assert "parent" not in PEAKS[0]["_links"].keys()
    assert "parent"     in PEAKS[1]["_links"].keys()
    assert "parent"     in PEAKS[2]["_links"].keys()
    assert "parent" not in PEAKS[3]["_links"].keys()
    assert "parent"     in PEAKS[4]["_links"].keys()

    PT.peaks.remove(peaktable.Peak(42.1234))
    PT.peaks.remove(peaktable.Peak(57.0815))
    r = API.sync(PT)
    assert 0 == r["added"]
    assert 0 == r["updated"]
    assert 3 == r["up-to-date"]
    assert 0 == r["linked"]
    assert 2 == r["unlinked"]

    j = API.get("/api/peaks?only=parents")
    assert j["count"] == 1

    j = API.get("/api/peaks?only=children")
    assert j["count"] == 1

    j = API.get("/api/peaks")
    PEAKS = j["_embedded"]["peaks"]

    ## no peaks are actually removed ?
    assert j["count"] == 5
    assert len(PEAKS) == 5

    ## the former fit-peaks have no longer a parent ?
    assert "parent" not in PEAKS[0]["_links"].keys()
    assert "parent" not in PEAKS[1]["_links"].keys()
    assert "parent"     in PEAKS[2]["_links"].keys()
    assert "parent" not in PEAKS[3]["_links"].keys()
    assert "parent" not in PEAKS[4]["_links"].keys()


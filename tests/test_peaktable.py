"""
Test of module pytrms.peaktable

"""
import logging

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


def test_save_and_reload(tmp_path, PT):
    #logging.warning(tmp_path)  # /tmp/pytest-of-morris/pytest-5/test_save_and_reload0/

    PT.save(tmp_path / "test1.ipta")

    READBACK = peaktable.PeakTable.from_file(tmp_path / "test1.ipta")

    assert len(READBACK) == len(PT)


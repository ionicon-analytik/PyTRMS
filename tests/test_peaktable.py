"""
Test of module pytrms.peaktable

"""
import logging

import pytest

from pytrms import peaktable


@pytest.fixture
def pt_with_nominal():
    """Create a comprehensive PeakTable with various peak types and properties."""
    return peaktable.PeakTable([
        # Basic nominal peaks
        peaktable.Peak(42.0,    label="H3O+", formula="H3O"),
        peaktable.Peak(57.0,    label="C2H5O+", formula="C2H5O"),
        # Peaks with custom properties
        peaktable.Peak(21.0219, label="H3O+_ref", formula="H3O", isotopic_abundance=0.678, k_rate=2.1, multiplier=488.0),
        peaktable.Peak(59.0121, label="C3H5O+", formula="C3H5O", isotopic_abundance=0.123, k_rate=1.5, multiplier=250.0),
        peaktable.Peak(75.0,    label="CustomBorder", borders=(74.5, 75.5)),
        peaktable.Peak(83.0,    label="HighRes", resolution=2000.0, shift=0.1),
        peaktable.Peak(100.0,   label="UnitMass"),
    ])


@pytest.fixture
def pt_with_fitted():
    """Create a PeakTable with parent-child relationships for formats that support it."""
    p_list = [
        peaktable.Peak(42.0, label="H3O+", formula="H3O"),
        peaktable.Peak(57.0, label="C2H5O+", formula="C2H5O"),
    ]
    # Add fitted peaks (children) with parent relationships
    p_list.append(peaktable.Peak(42.1234, label="H3O+_fit1", parent=p_list[0], formula="H3O"))
    p_list.append(peaktable.Peak(42.2345, label="H3O+_fit2", parent=p_list[0], formula="H3O"))

    return peaktable.PeakTable(p_list)


## -------- ===== ++++ ===== --------- ##


def test_props(pt_with_fitted):
    assert len(pt_with_fitted) == 4

    assert pt_with_fitted.nominal
    assert pt_with_fitted.fitted
    assert pt_with_fitted.mass_labels


def test_sorted(pt_with_fitted):
    assert len(pt_with_fitted) == 4

    assert pt_with_fitted.exact_masses == [42.0, 42.1234, 42.2345, 57.0]
    assert pt_with_fitted.mass_labels == ["H3O+", "H3O+_fit1", "H3O+_fit2", "C2H5O+"]


def test_find_by_mass(pt_with_fitted):
    assert len(pt_with_fitted) == 4

    assert pt_with_fitted.find_by_mass(42.    ) == peaktable.Peak(42.    )
    assert pt_with_fitted.find_by_mass(57.    ) == peaktable.Peak(57.    )
    assert pt_with_fitted.find_by_mass(42.1234) == peaktable.Peak(42.1234)
    assert pt_with_fitted.find_by_mass(42.2345) == peaktable.Peak(42.2345)

    with pytest.raises(KeyError):
        pt_with_fitted.find_by_mass(3.14159)


@pytest.mark.parametrize("format_ext", [
    ".ipta",    # LabView INI-style
    ".ipt",     # LabView tab-separated  
    ".json",    # JSON format
    ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_round_trip_empty_peaktable(tmp_path, format_ext):
    """Test round-trip with empty PeakTable."""
    empty_pt = peaktable.PeakTable([])
    
    filename = tmp_path / f"empty{format_ext}"
    empty_pt.save(filename)
    
    reloaded = peaktable.PeakTable.from_file(filename)
    
    assert len(reloaded) == 0
    assert len(reloaded.nominal) == 0
    assert len(reloaded.fitted) == 0


@pytest.mark.parametrize("format_ext", [
    ".ipta",    # LabView INI-style
    ".ipt",     # LabView tab-separated  
    ".json",    # JSON format
    ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_round_trip_nominal_only(tmp_path, pt_with_nominal, format_ext):
    """Test round-trip functionality for formats that work with nominal peaks only."""
    # Save the PeakTable
    filename = tmp_path / f"test{format_ext}"
    pt_with_nominal.save(filename)

    # Load it back
    reloaded = peaktable.PeakTable.from_file(filename)

    # Validate PeakTable-level properties
    assert len(reloaded) == len(pt_with_nominal)

    assert len(pt_with_nominal.fitted) == 0
    assert len(reloaded.fitted) == 0

    assert pt_with_nominal.exact_masses == reloaded.exact_masses

    for orig, reloaded in zip(pt_with_nominal, reloaded):
        assert orig.center     == reloaded.center
        assert orig.label      == reloaded.label
        assert orig.borders    == reloaded.borders
        assert orig.k_rate     == reloaded.k_rate
        assert orig.multiplier == reloaded.multiplier


@pytest.mark.parametrize("format_ext", [
#   ".json",    # JSON format
#   ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_round_trip_with_fitted(tmp_path, pt_with_fitted, format_ext):
    """Test round-trip with fitted peaks using JSON formats."""
    filename = tmp_path / f"test{format_ext}"
    pt_with_fitted.save(filename)

    # Load it back
    reloaded = peaktable.PeakTable.from_file(filename)

    # Validate PeakTable-level properties
    assert len(reloaded) == len(pt_with_fitted)

    assert len(pt_with_fitted.fitted) > 0
    assert len(reloaded.fitted) == len(pt_with_fitted.fitted)

    assert pt_with_fitted.exact_masses == reloaded.exact_masses
    assert pt_with_fitted.mass_labels == reloaded.mass_labels

    for orig, reloaded in zip(pt_with_fitted, reloaded):
        assert orig.center     == reloaded.center
        assert orig.label      == reloaded.label
        assert orig.borders    == reloaded.borders
        assert orig.k_rate     == reloaded.k_rate
        assert orig.multiplier == reloaded.multiplier


def test_write_ionipt(pt_with_fitted):
    EXPECT = r"""[
    {
        "border_peak": {
            "name": "H3O+",
            "center": 42.0,
            "ion": "",
            "ionic_isotope": "H3O",
            "parent": "",
            "isotopic_abundance": 1.0,
            "k_rate": 2.0,
            "multiplier": 1.0,
            "resolution": 1000.0
        },
        "low": 41.5,
        "high": 42.5,
        "peak": [
            {
                "name": "H3O+_fit1",
                "center": 42.1234,
                "ion": "",
                "ionic_isotope": "H3O",
                "parent": "",
                "isotopic_abundance": 1.0,
                "k_rate": 2.0,
                "multiplier": 1.0,
                "resolution": 1000.0
            },
            {
                "name": "H3O+_fit2",
                "center": 42.2345,
                "ion": "",
                "ionic_isotope": "H3O",
                "parent": "",
                "isotopic_abundance": 1.0,
                "k_rate": 2.0,
                "multiplier": 1.0,
                "resolution": 1000.0
            }
        ],
        "mode": 3,
        "shift": 0.0
    },
    {
        "border_peak": {
            "name": "C2H5O+",
            "center": 57.0,
            "ion": "",
            "ionic_isotope": "C2H5O",
            "parent": "",
            "isotopic_abundance": 1.0,
            "k_rate": 2.0,
            "multiplier": 1.0,
            "resolution": 1000.0
        },
        "low": 56.5,
        "high": 57.5,
        "peak": [],
        "mode": 1,
        "shift": 0.0
    }
]"""
    from io import StringIO

    with StringIO(newline='\n') as fp:
        pt_with_fitted._write_ionipt(fp)
        READBACK = fp.getvalue()

    assert len(READBACK) == len(EXPECT)
#   assert READBACK == EXPECT


def test_read_ionipt_meets_requirements():
    SUT = peaktable.PeakTable.from_file("./tests/Sony_peak-table_260126_fits.ionipt")

    assert len(SUT) == 8

    # check some peaks (PerMasCal)...

    assert SUT[1] == 329.8400
    assert SUT[1].label == "*(C6H4I2)+"

    assert SUT[2] == 330.0
    assert SUT[2].label == "m330"

    assert SUT[3] == 330.8480
    assert SUT[3].label == "*(C6H4I2)H+"

    assert SUT[4] == 330.8480
    assert SUT[4].label == "m331_fit_C6H4I2H+"

    assert SUT[5] == 331.0
    assert SUT[5].label == "m331"

    assert SUT[6] == 331.850891
    assert SUT[6].label == "*(C6H4I2)H+ i"

    assert SUT[7] == 332.0
    assert SUT[7].label == "m332"

    # check the Reference-peak can be found...

    REF = SUT.find_by_mass(330.847992)
    assert REF == 330.8480
    assert REF.parent is None
#   assert REF.label == "m331_fit_C6H4I2H+"


def test_read_ionipt_solves_issue_3433():
    SUT = peaktable.PeakTable.from_file("./tests/issue_3433.ionipt")

    assert len(SUT) == 5

    assert SUT.mass_labels == ["m100_o", "C4H5NS", "C4H5NS_H+", "m100_o_Peak1", "m100_o_Peak2"]

    # check the peaks' exact masses...

    assert SUT[0] == 100.0
    assert SUT[0].label == "m100_o"

    assert SUT[1] == 100.021545
    assert SUT[1] == 100.0215
    assert SUT[1].label == "C4H5NS"

    assert SUT[2] == 100.02196
    assert SUT[2] == 100.0220
    assert SUT[2].label == "C4H5NS_H+"

    assert SUT[3] == 100.0429
    assert SUT[3].label == "m100_o_Peak1"

    assert SUT[4] == 100.0792
    assert SUT[4].label == "m100_o_Peak2"


"""
Test of module pytrms.peaktable

"""
import logging

import pytest

from pytrms import peaktable


@pytest.fixture
def comprehensive_pt():
    """Create a comprehensive PeakTable with various peak types and properties."""
    peaks = [
        # Basic nominal peaks
        peaktable.Peak(42.0, label="H3O+", formula="H3O"),
        peaktable.Peak(57.0, label="C2H5O+", formula="C2H5O"),
        
        # Peaks with custom properties
        peaktable.Peak(21.0219, label="H3O+_ref", formula="H3O", 
                      isotopic_abundance=0.678, k_rate=2.1, multiplier=488.0),
        peaktable.Peak(59.0121, label="C3H5O+", formula="C3H5O",
                      isotopic_abundance=0.123, k_rate=1.5, multiplier=250.0),
        
        # Peaks with custom borders
        peaktable.Peak(75.0, label="CustomBorder", borders=(74.5, 75.5)),
        
        # Peaks with resolution and shift
        peaktable.Peak(83.0, label="HighRes", resolution=2000.0, shift=0.1),
        
        # Unit mass peaks
        peaktable.Peak(100.0, label="UnitMass"),
    ]
    
    return peaktable.PeakTable(peaks)


@pytest.fixture
def pt_with_fitted():
    """Create a PeakTable with parent-child relationships for formats that support it."""
    peaks = [
        peaktable.Peak(42.0, label="H3O+", formula="H3O"),
        peaktable.Peak(57.0, label="C2H5O+", formula="C2H5O"),
    ]
    
    pt = peaktable.PeakTable(peaks)
    
    # Add fitted peaks (children) with parent relationships
    pt.peaks.append(peaktable.Peak(42.1234, label="H3O+_fit1", 
                                   parent=pt.peaks[0], formula="H3O"))
    pt.peaks.append(peaktable.Peak(42.2345, label="H3O+_fit2", 
                                   parent=pt.peaks[0], formula="H3O"))
    
    return pt




def validate_format_specific_properties(original, reloaded, format_ext):
    """Validate PeakTable round-trip with format-specific considerations."""
    if format_ext in ['.ipta', '.ipt']:
        # .ipta and .ipt formats don't preserve parent-child relationships
        # All peaks become nominal after reload
        assert len(reloaded.fitted) == 0

    # Focus on core properties that should be preserved
    for orig_peak, reloaded_peak in zip(original.peaks, reloaded.peaks):
        # Center mass should always be preserved
        assert orig_peak.center     == reloaded_peak.center
        assert orig_peak.label      == reloaded_peak.label
        assert orig_peak.borders    == reloaded_peak.borders
        assert orig_peak.k_rate     == reloaded_peak.k_rate
        assert orig_peak.multiplier == reloaded_peak.multiplier


@pytest.mark.parametrize("format_ext", [
    ".ipta",    # LabView INI-style
    ".ipt",     # LabView tab-separated  
    ".json",    # JSON format
    ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_round_trip_nominal_only(tmp_path, comprehensive_pt, format_ext):
    """Test round-trip functionality for formats that work with nominal peaks only."""
    # Save the PeakTable
    filename = tmp_path / f"test{format_ext}"
    comprehensive_pt.save(filename)
    
    # Load it back
    reloaded = peaktable.PeakTable.from_file(filename)
    
    # Validate PeakTable-level properties
    assert len(reloaded) == len(comprehensive_pt)
    
    # For .ipta and .ipt formats, parent-child relationships are lost
    if format_ext in ['.ipta', '.ipt']:
        assert len(reloaded.fitted) == 0
    else:
        assert len(reloaded.fitted) == len(comprehensive_pt.fitted)
    
    # Validate exact masses
    assert reloaded.exact_masses == comprehensive_pt.exact_masses
    
    # Format-specific validation
    validate_format_specific_properties(comprehensive_pt, reloaded, format_ext)


@pytest.mark.parametrize("format_ext", [
#   ".ipta",    # LabView INI-style
#   ".ipt",     # LabView tab-separated  
#   ".json",    # JSON format
#   ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_round_trip_with_fitted_json(tmp_path, pt_with_fitted, format_ext):
    """Test round-trip with fitted peaks using JSON formats."""
    filename = tmp_path / f"test_fitted{format_ext}"
    pt_with_fitted.save(filename)
    
    reloaded = peaktable.PeakTable.from_file(filename)
    
    # Basic validation - at least the peak count should be preserved
    assert len(reloaded) == len(pt_with_fitted)
    
    # Comprehensive validation for JSON formats
    validate_format_specific_properties(pt_with_fitted, reloaded, format_ext)


@pytest.mark.parametrize("format_ext", [
    ".ipta",    # LabView INI-style
    ".ipt",     # LabView tab-separated  
    ".json",    # JSON format
    ".ipt3",    # JSON format (same as .json)
    ".ionipt",  # modern JSON format (best compatibility)
])
def test_empty_peaktable_round_trip(tmp_path, format_ext):
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
def test_nominal_only_peaktable(tmp_path, format_ext):
    """Test round-trip with only nominal peaks."""
    nominal_only = peaktable.PeakTable([
        peaktable.Peak(42.0, label="H3O+", formula="H3O"),
        peaktable.Peak(57.0, label="C2H5O+", formula="C2H5O"),
    ])
    
    filename = tmp_path / f"nominal{format_ext}"
    nominal_only.save(filename)
    
    reloaded = peaktable.PeakTable.from_file(filename)
    
    assert len(reloaded) == 2
    assert len(reloaded.nominal) == 2
    assert len(reloaded.fitted) == 0
    
    validate_format_specific_properties(nominal_only, reloaded, format_ext)


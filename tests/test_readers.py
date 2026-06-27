####################################################
#                                                  #
# testing testing testing                          #
#                                                  #
####################################################
import pytest

import re

from pytrms import readers


class TestReaders:

    def test_one(self):
        assert True

    @pytest.mark.parametrize('match_fun', [
        "AddTraces/PTR-Reaction",   # exact location
        "PTR-Reaction",             # location w/o AddTraces group
        "PTR-React[a-z]+",          # regex (no group-name!)
        re.compile(".*/PTR-React[a-z]+"), # compiled regex (with group-name!)
        lambda g: "React" in g,     # filter-function
        lambda s: s.endswith("Reaction") # different filter-function
    ])
    def test_read_addtraces_matches_location(self, match_fun):

        SUT = readers.IoniTOFReader('../../Zeiss20/AMEData/2025_12_16__12_42_31/2025_12_16__12_42_31.h5')

        assert "AddTraces/PTR-Reaction" in SUT._locate_datainfo()

        t = SUT.read_addtraces(match_fun)
        assert t.shape == (40, 6)

        assert 'DPS_Udrift_Act' in t.columns
        assert 'Press_Drift_Act' in t.columns
        assert 'T-Drift_Act' in t.columns
        assert 'E_N_Act' in t.columns



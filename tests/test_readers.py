####################################################
#                                                  #
# testing testing testing                          #
#                                                  #
####################################################
import pytest

import os
import re

from pytrms import readers

WORKDIR = os.path.dirname(__file__)


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

        TESTFILE = os.path.join(WORKDIR, "../examples/data/peter_emmes_2022-03-31_09-10-08.h5")

        SUT = readers.IoniTOFReader(TESTFILE)

        assert "AddTraces/PTR-Reaction" in SUT._locate_datainfo()

        t = SUT.read_addtraces(match_fun)
        assert t.shape == (129, 6)

        # note: maybe not the latest exact names, but those are in that file:
        assert "Udrift_Act" in t.columns
        assert "p-Drift_Act" in t.columns
        assert "T-Drift_Act" in t.columns
        assert "E/N_Act" in t.columns



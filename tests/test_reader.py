####################################################
#                                                  #
# testing testing testing                          #
#                                                  #
####################################################
import pytest

import os.path


class TestMeasurement:

    def test_one(self):
        assert os.path.exists('examples/data')




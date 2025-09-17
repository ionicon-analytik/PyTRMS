import os

from .. import enable_extended_logging

_root = os.path.dirname(__file__)
_par_id_file = os.path.abspath(os.path.join(_root, '..', 'data', 'ParaIDs.csv'))
assert os.path.exists(_par_id_file), "par-id file not found: please re-install PyTRMS package"



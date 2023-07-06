"""Module instrument.py

"""
import logging

import numpy as np

from ._base import TPSAdapter

__all__ = ['Instrument']

log = logging.getLogger(__name__)


class InstReader(TPSAdapter):
    """Analogue for a real-world IoniTOF instrument.

    """
    def __init__(self, h5file, cursor):
        self.h5f = h5file
        self.cursor = cursor

    @property
    def inst_type(self):
        return str(self.h5f.attrs.get('InstrumentType', [b'',])[0].decode('latin-1'))

    @property
    def sub_type(self):
        return str(self.h5f.attrs.get('InstSubType', [b'',])[0].decode('latin-1'))

    @property
    def serial(self):
        return str(self.h5f.attrs.get('InstSerial#', [b'',])[0].decode('latin-1'))

    @serial.setter
    def serial(self, number):
        self.h5f.attrs['InstSerial#'] = np.array([str(number).encode()], dtype='S')
        self.h5f.flush()

    def act_values(self):
        info = self.h5f.get('AddTraces/TofSupply/Info')
        data = self.h5f.get('AddTraces/TofSupply/Data')
        if not data.shape[1] == info.shape[1]:
            log.error("No TOF-Supply data available in %r!" % self)
            return dict()

        keys = [s.decode('latin-1') for s in info[0, :] if s]
        units = [s.decode('latin-1') for s in info[1, :] if s]
        values = data[self.cursor()]
        if keys[0].endswith('[Set]'):
            rv = {key[:-5]: (value, unit)
                  for key, value, unit in zip(keys, values, units)
                  if key.endswith('[Set]')}
        else:
            rv = {key: (value, unit)
                  for key, value, unit in zip(keys, values, units)}

        return rv

    def act_value(self, key):
        return self.act_values()[key]

    def set_value(self, key, value, unit):
        raise PermissionError("Cannot set the TPS-voltage on a .h5-file!")

    def set_values(self, values):
        raise PermissionError("Cannot set the TPS-voltage on a .h5-file!")

    def __repr__(self):
        return "<%s %s [no. %s]>" % (self.inst_type, self.sub_type, self.serial)

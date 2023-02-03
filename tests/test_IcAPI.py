"""Test of module pytrms.modbus

"""
import pytest

import icapi

ip = '127.0.0.1'  # loopback


class TestIcAPI:

#   def test_unpack(self):
#       assert IoniconModbus._unpack([17448, 0]) == 672

#       with pytest.raises():
#           IoniconModbus._unpack([17, 44, 6])

    def test_one(self):
        icapi.GetNumberOfTimebins(ip)
        #assert IoniconModbus._unpack(IoniconModbus._pack(42)) == 42


#icapi.GetCurrentDataFileName(ip).rstrip('\x00')
#icapi.GetCurrentSpectrum(ip)
#rc, ac, rt, at, spec = icapi.GetCurrentSpectrum(ip)
#import time
#from time import monotonic as clock
#    
#if True:
#    t0 = clock()
#    for i in range(1000):
#        icapi.GetCurrentSpectrum(ip)
#    print('took:', (clock()-t0)/1000, 's')
#    
#spec
#max(spec)
#import numpy as np
#np.median(spec)
#np.mean(spec)
#np.sum(spec)/1000

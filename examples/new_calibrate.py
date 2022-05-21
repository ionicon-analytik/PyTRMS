#################################################
#                                               #
# Script to calibrate                           #
#                                               #
#################################################
import os
import time
import json

import pytrms

myPTRSET_BK = 4
myPTRSET_QC = 5
myPTRSET_Sample = 6

client = pytrms.connect('127.0.0.1', port=8002)

mm = pytrms.Measurement('D:/Data/calibration.h5', client)
mm.set('OP_Mode', myPTRSET_BK)
mm.wait(60, 'Flushing...')
mm.start()
mm.wait(120, 'Flushing...')
mm.set('OP_Mode', myPTRSET_QC)
mm.wait(180, 'Flushing...')
mm.stop()
mm.set('OP_Mode', myPTRSET_Sample)
mm.wait(60, 'Flushing...')

print('Done!!')


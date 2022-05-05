#################################################
#                                               #
# Script to calibrate                           #
#                                               #
#################################################
import os
import time
import json

import ioniclient

myPTRSET_BK = 4
myPTRSET_QC = 5
myPTRSET_Sample = 6

client = ioniclient.IoniClient('127.0.0.1', port=8002)

print('# Calibration measurment')
folder = os.path.join('D:', 'Data')
os.makedirs(folder, exist_ok=True)
filename = time.strftime("Cal_%Y-%m-%d_%H-%M-%S", time.localtime())
path = os.path.join(folder, filename)

print('Setting BK')
client.set('OP_Mode', myPTRSET_BK)
time.sleep(60) # to flush
print('Start Measurement')
print(client.start_measurement(path))
time.sleep(120) # to flush
print('Set QC')
client.set('OP_Mode', myPTRSET_QC)
time.sleep(180) # to flush
print(client.stop_measurement())
print('Measurement Stopped. Flushing.')
client.set('OP_Mode', myPTRSET_Sample)
time.sleep(60) # to flush
print('Done!!')

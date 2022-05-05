#################################################
#                                               #
# Script zum definierten Breath Messen          #
#                                               #
#################################################
import os
import time
import json
import winsound

import ioniclient

def BeepStart():
    pass
    #winsound.Beep(440, 500)
    #winsound.Beep(660, 500)
    #winsound.Beep(880, 500)

def BeepStop():
    #winsound.Beep(660, 500)
    #winsound.Beep(330, 1500)
    pass

client = ioniclient.IoniClient('127.0.0.1', port=8002)

filename = time.strftime("jens_%Y-%m-%d_%H-%M-%S", time.localtime())

print('Startig breath measurement with filename:\t',filename)
print('Wait to exhale until told.')
folder = os.path.join('D:', 'Data')
os.makedirs(folder, exist_ok=True)
path = os.path.join(folder, filename)

client.start_measurement(path)
time.sleep(10)
print('Exhale now.')
time.sleep(110)
print('Ready to stop')
time.sleep(10)
client.stop_measurement()
print('Breath measurement stopped.')


filename = time.strftime("BK_%Y-%m-%d_%H-%M-%S", time.localtime())
path = os.path.join(folder, filename)

print('Commencing with BG measurment in 1 min to:\t', filename)
time.sleep(60)
client.start_measurement(path)
print('BG Started / 120 s to go')
time.sleep(30)
print('90s to go')
time.sleep(30)
print('60s to go')
time.sleep(30)
print('30s to go')
time.sleep(30)
client.stop_measurement()
print('BG Stopped')
print('---------------------------------')
print('Ready...')


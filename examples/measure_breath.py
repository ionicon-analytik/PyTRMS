#################################################
#                                               #
# Script for defined breath measurements.       #
#                                               #
# > see 'breath_processing.py' for analysis!    #
#                                               #
#################################################
import time

import pytrms

try:
    from winsound import Beep
except ModuleNotFoundError:
    Beep = print
    Beep("run `pip install winsound` for the real experience")


def BeepStart():
    Beep(440, 500)
    Beep(660, 500)
    Beep(880, 500)

def BeepStop():
    Beep(660, 500)
    Beep(330, 1500)


ptr = pytrms.connect('localhost')

patient = input('please enter your name: ')
filename = patient.replace(' ', '_') + '_%Y-%m-%d_%H-%M-%S.h5'
path = 'D:/Data/' + filename

print('please wait to exhale until told.')

ptr.start_measurement(path)
time.sleep(10)

BeepStart()
print('Exhale now!')
time.sleep(75)

print('Ready to stop.')
time.sleep(10)
BeepStop()

ptr.stop_measurement()

print('commencing with background measurement in 1 minute...')
time.sleep(60)

ptr.start_measurement('D:/Data/BK_%Y-%m-%d_%H-%M-%S.h5')

print('BG Started / 120 s to go')
time.sleep(120)

ptr.stop_measurement()

print('thank you. please start over again...')

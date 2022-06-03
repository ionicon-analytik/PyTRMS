#################################################
#                                               #
# Script for defined breath measurements        #
#                                               #
#################################################
import winsound
import pytrms


def BeepStart():
    winsound.Beep(440, 500)
    winsound.Beep(660, 500)
    winsound.Beep(880, 500)

def BeepStop():
    winsound.Beep(660, 500)
    winsound.Beep(330, 1500)


ptr = pytrms.connect('localhost')

patient = input('please enter your name: ')
filename = patient.replace(' ', '_') + '_%Y-%m-%d_%H-%M-%S.h5'
path = 'D:/Data/' + filename

print('please wait to exhale until told.')

ptr.start(path)
time.sleep(10)

BeepStart()
print('Exhale now!')
time.sleep(110)

print('Ready to stop.')
time.sleep(10)
BeepStop()

ptr.stop()

filename = time.strftime(, time.localtime())
path = os.path.join(folder, filename)

print('commencing with BG measurement in 1 minute...')
time.sleep(60)

ptr.start('D:/Data/BK_%Y-%m-%d_%H-%M-%S.h5')

print('BG Started / 120 s to go')
time.sleep(120)

ptr.stop()

print('thank you. please start over again...')


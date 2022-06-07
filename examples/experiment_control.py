##########################################################
#                                                        #
# example script for starting and stopping measurements  #
#                                                        #
# this assumes, that a PTR instrument is connected to    #
# the local computer and is running a 'webAPI' server    #
#                                                        #
##########################################################
try:
    import pytrms
except ModuleNotFoundError:
    # find module if running from the example folder
    # in a cloned repository from GitHub:
    sys.path.insert(0, join(dirname(__file__), '..'))
    import pytrms

ptr = pytrms.connect('localhost')

myPTRSET_BK = 4
myPTRSET_QC = 5
myPTRSET_Sample = 6

filename = "Cal_%Y-%m-%d_%H-%M-%S.h5"

print('flushing in BK mode for 60 seconds...')
ptr.set('OP_Mode', myPTRSET_BK)
time.sleep(60)

ptr.start(filename)
time.sleep(120)

print('flushing in QC mode for 180 seconds...')
ptr.set('OP_Mode', myPTRSET_QC)
time.sleep(180)

ptr.stop()
print('flushing in Sample mode for 60 seconds...')
client.set('OP_Mode', myPTRSET_Sample)
time.sleep(60)

print('Done.')


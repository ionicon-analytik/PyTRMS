from collections import namedtuple

# Note: this object has almost the same set of attributes as the
#  mqtt 'Message' object, but avoids copying the RLock!
#  furthermore, the order of arguments is the same as that of
#  the paho.mqtt 'publish()' function and can be easily applied:
msg_info = namedtuple('msg_info', ['timestamp', 'topic', 'payload', 'qos', 'retain'])

from .recorder import Recorder


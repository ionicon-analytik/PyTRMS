_version = '0.9.8'

import logging
from functools import wraps

_logging_getLogger = logging.getLogger

@wraps(_logging_getLogger)
def getLoggerWithAnnouncement(name=None):
    # patch the (global) logger to print its own name
    #  (useful for turning individual loggers on/off)
    # WARNING: this will patch every instance of the
    #  logging-module in every import after pytrms is
    #  imported! don't be overwhelmingly fancy with this!
    rv = _logging_getLogger(name)
    if name is not None:
        rv.debug(f"'acquired logger for '{name}'")

    return rv

logging.getLogger = getLoggerWithAnnouncement
logging.TRACE = 5  # even more verbose than logging.DEBUG

__all__ = ['load', 'connect']


def enable_extended_logging(log_level=logging.DEBUG):
    '''make output of http-requests more talkative.

    set 'log_level=logging.TRACE' for highest verbosity!
    '''
    if log_level <= logging.DEBUG:
        # enable logging of http request urls on the library, that is
        #  underlying the 'requests'-package:
        logging.warning(f"enabling logging-output on 'urllib3' ({log_level = })")
        requests_log = logging.getLogger("urllib3")
        requests_log.setLevel(log_level)
        requests_log.propagate = True

    if log_level <= logging.TRACE:
        # Enabling debugging at http.client level (requests->urllib3->http.client)
        # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with
        # HEADERS but without DATA. the only thing missing will be the response.body,
        # which is not logged.
        logging.warning(f"enabling logging-output on 'HTTPConnection' ({log_level = })")
        from http.client import HTTPConnection
        HTTPConnection.debuglevel = 1


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    `path` may be a glob-expression to collect a whole batch.

    returns a `Measurement` instance.
    '''
    import glob
    from .measurement import FinishedMeasurement

    files = glob.glob(path)

    return FinishedMeasurement(*files)


def connect(host='localhost', port=None, method='mqtt'):
    '''Connect a client to a running measurement server.

    'method' is the preferred connection, either 'mqtt' (default), 'webapi' or 'modbus'.

    returns an `Instrument` if connected successfully.
    '''
    from .instrument import Instrument

    if method.lower() == 'mqtt':
        from .clients.mqtt import MqttClient as _client
    elif method.lower() == 'webapi':
        from .clients.ioniclient import IoniClient as _client
    elif method.lower() == 'modbus':
        from .clients.modbus import IoniconModbus as _client
    else:
        raise NotImplementedError(str(method))

    backend = _client(host, port) if port is not None else _client(host)

    return Instrument(backend)


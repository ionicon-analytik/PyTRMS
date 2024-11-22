import os

_root = os.path.dirname(__file__)
_par_id_file = os.path.abspath(os.path.join(_root, '..', 'data', 'ParaIDs.csv'))
assert os.path.exists(_par_id_file), "par-id file not found: please re-install PyTRMS package"


import logging as _logging

_logging.TRACE = 5  # even more verbose than logging.DEBUG

def enable_extended_logging(log_level=_logging.DEBUG):
    '''make output of http-requests more talkative.
    
    set 'log_level=logging.TRACE' (defined as 0 in pytrms.__init__) for highest verbosity!
    '''
    if log_level <= _logging.DEBUG:
        # enable logging of http request urls on the library, that is
        #  underlying the 'requests'-package:
        _logging.warn(f"enabling logging-output on 'urllib3' ({log_level = })")
        requests_log = _logging.getLogger("urllib3")
        requests_log.setLevel(log_level)
        requests_log.propagate = True
    
    if log_level <= _logging.TRACE:
        # Enabling debugging at http.client level (requests->urllib3->http.client)
        # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with
        # HEADERS but without DATA. the only thing missing will be the response.body,
        # which is not logged.
        _logging.warn(f"enabling logging-output on 'HTTPConnection' ({log_level = })")
        from http.client import HTTPConnection
        HTTPConnection.debuglevel = 1


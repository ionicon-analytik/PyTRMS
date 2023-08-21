import logging

logging.TRACE = 0

log = logging.getLogger('pytrms')

if log.level <= logging.DEBUG:
    # enable logging of http request urls on the underlying library of the
    # 'requests'-package:
    requests_log = logging.getLogger("urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

if log.level == logging.TRACE:
    # Enabling debugging at http.client level (requests->urllib3->http.client)
    # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with
    # HEADERS but without DATA. the only thing missing will be the response.body,
    # which is not logged.
    from http.client import HTTPConnection
    HTTPConnection.debuglevel = 1


import os

ionitof_host = str(os.environ.get('IONITOF_HOST', '127.0.0.1'))
ionitof_port = int(os.environ.get('IONITOF_PORT', 8002))

database_host = str(os.environ.get('DATABASE_HOST', '127.0.0.1'))
database_port = int(os.environ.get('DATABASE_PORT', 5066))


import re
from collections import namedtuple
from collections.abc import Iterable

import requests

from . import _logging

log = _logging.getLogger()

_event_rv = namedtuple('ssevent', ['event', 'data'])

class SSEventListener(Iterable):

    @staticmethod
    def _line_stream(response):
        # Note: using .iter_content() seems to yield results faster than .iter_lines()
        line = ''
        for bite in response.iter_content(chunk_size=1, decode_unicode=True):
            line += bite
            if bite == '\n':
                yield line
                line = ''

    def __init__(self, event_re=None, host_url='http://127.0.0.1:5066',
            endpoint='/api/events', session=None):
        self.uri = host_url + endpoint
        if session is not None:
            self._get = session.get
        else:
            self._get = requests.get
        self._connect_response = None
        self.subscriptions = set()
        if event_re is not None:
            self.subscribe(event_re)

    def subscribe(self, event_re):
        """Listen for events matching the given string or regular expression."""
        self.subscriptions.add(re.compile(event_re))
        if self._connect_response is None:
            r = self._get(self.uri, headers={'accept': 'text/event-stream'}, stream=True)
            if not r.ok:
                log.error(f"no connection to {self.uri} (got [{r.status_code}])")
                r.raise_for_status()

            self._connect_response = r

    def unsubscribe(self, event_re):
        """Stop listening for certain events."""
        self.subscriptions.remove(re.compile(event_re))
        if not len(self.subscriptions):
            log.debug(f"closing connection to {self.uri}")
            self._connect_response.close()
            self._connect_response = None

    def __iter__(self):
        if self._connect_response is None:
            raise Exception("call .subscribe() first to listen for events")

        event = msg = ''
        for line in self._line_stream(self._connect_response):  # blocks...
            if not line.strip():
                # an empty line concludes an event
                if event and any(re.match(sub, event) for sub in self.subscriptions):
                    yield _event_rv(event, msg)

                # Note: any further empty lines are ignored (may be used as keep-alive),
                #  but in either case clear event and msg to rearm for the next event:
                event = msg = ''

            key, val = line.split(':', maxsplit=1)
            if not key:
                # this is a comment, starting with a colon ':' ...
                log.log(_logging.TRACE, "sse:" + val)
            elif key == 'event':
                event = val.lstrip()
            elif key == 'data':
                msg += val.lstrip()
            else:
                log.warning(f"unknown SSE-key <{key}> in stream")


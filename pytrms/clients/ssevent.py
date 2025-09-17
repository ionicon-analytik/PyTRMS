import re
import time
import logging
from collections import namedtuple
from collections.abc import Iterable

import requests

log = logging.getLogger(__name__)

_event_rv = namedtuple('ssevent', ['event', 'data'])


class SSEventListener(Iterable):

    @staticmethod
    def _line_stream(response):
        # Note: using .iter_content() seems to yield results faster than .iter_lines()
        line = ''
        for bite in response.iter_content(chunk_size=1, decode_unicode=True):
            line += bite
            if bite == '\n':
                yield line.strip()
                line = ''

    def __init__(self, event_re=None, host_url='http://127.0.0.1:5066',
            endpoint='/api/events', session=None):
        self.uri = host_url + endpoint
        if session is not None:
            self._get = session.get
        else:
            self._get = requests.get
        self.subscriptions = set()
        if event_re is not None:
            self.subscribe(event_re)

    def subscribe(self, event_re):
        """Listen for events matching the given string or regular expression."""
        self.subscriptions.add(re.compile(event_re))

    def unsubscribe(self, event_re):
        """Stop listening for certain events."""
        self.subscriptions.remove(re.compile(event_re))

    def follow_events(self, timeout_s=None):
        """Returns a generator that produces events as soon as they are emitted.

        When `timeout_s` is given, a hard timeout is set, after which the stream
        is closed and the generator raises `StopIteration`. This makes it possible
        to e.g. collect events into a list or test for an event to occur.

        _Note_: The timeout cannot be accurate, because the `requests` library only
         allows to check the timeout when either an event or a keep-alive is received!
         This may take up to 13 seconds (currently set on the API). Also, the last
         event may be discarded.

        `iter(<instance>)` calls this method with `timeout_s=None`.
        """
        if not len(self.subscriptions):
            raise Exception("call .subscribe() first to listen for events")

        log.debug(f"opening connection to {self.uri}")
        _response = self._get(self.uri, headers={'accept': 'text/event-stream'}, stream=True)
        if not _response.ok:
            log.error(f"no connection to {self.uri} (got [{_response.status_code}])")
            _response.raise_for_status()

        started_at = time.monotonic()
        event = msg = ''
        try:
            for line in self._line_stream(_response):  # blocks...
                elapsed_s = time.monotonic() - started_at
                if timeout_s is not None and elapsed_s > timeout_s:
                    log.debug(f"no more events after {round(elapsed_s)} seconds")
                    return  # (raises StopIteration)

                if not line:
                    # an empty line concludes an event
                    if event and any(re.match(sub, event) for sub in self.subscriptions):
                        yield _event_rv(event, msg)

                    # Note: any further empty lines are ignored (may be used as keep-alive),
                    #  but in either case clear event and msg to rearm for the next event:
                    event = msg = ''
                    continue

                key, val = line.split(':', maxsplit=1)
                if not key:
                    # this is a comment, starting with a colon ':' ...
                    log.log(logging.TRACE, "sse:" + val)
                elif key == 'event':
                    event = val.lstrip()
                elif key == 'data':
                    msg += val.lstrip()
                else:
                    log.warning(f"unknown SSE-key <{key}> in stream")
        finally:
            _response.close()
            log.debug(f"closed connection to {self.uri}")

    def __iter__(self):
        yield from self.follow_events(timeout_s=None)


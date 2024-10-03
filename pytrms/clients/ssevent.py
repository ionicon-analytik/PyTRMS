import re
import logging
from collections.abc import Iterable

import requests

from . import ionitof_url

log = logging.getLogger()


class SSEventListener(Iterable):

    def __init__(self, endpoint=''):
        if not endpoint:
            endpoint = ionitof_url + '/api/timing/stream'
        self.endpoint = endpoint
        self._response = None
        self.subscriptions = set()

    def subscribe(self, event='cycle'):
        """Listen for events matching the given string or regular expression.

        This will already match if the string is contained in the event-topic.
        """
        if self._response is None:
            r = requests.get(self.endpoint, headers={'accept': 'text/event-stream'}, stream=True)
            if not r.ok:
                log.error(f"no connection to {self.endpoint} (got [{r.status_code}])")
                r.raise_for_status()

            self._response = r

        regex = re.compile('.*' + event + '.*')  # be rather loose with matching..
        self.subscriptions.add(regex)

    def unsubscribe(self, event='cycle'):
        self.subscriptions.remove(event)
        if not len(self.subscriptions):
            log.debug(f"closing connection to {self.endpoint}")
            self._response.close()
            self._response = None

    @staticmethod
    def line_stream(response):
        # Note: using .iter_content() seems to yield results faster than .iter_lines()
        line = ''
        for bite in response.iter_content(chunk_size=1, decode_unicode=True):
            line += bite
            if bite == '\n':
                yield line
                line = ''

    def items(self):
        for msg in self:
            yield self.event, msg

    def __iter__(self):
        if self._response is None:
            raise Exception("call .subscribe() first to listen for events")

        for line in self.line_stream(self._response):  # blocks...
            if not line.strip():
                continue

            key, msg = line.split(':', maxsplit=1)
            msg = msg.strip()
            if key == 'event':
                self.event = msg

                if not any(sub.match(self.event) for sub in self.subscriptions):
                    log.debug(f"skipping event <{msg}>")
                    continue

            elif key == 'data':
                yield msg

            else:
                log.warning(f"skipping unknown key <{key}> in stream")
                continue



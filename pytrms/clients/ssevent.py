from collections.abc import Iterable
import logging

import requests

from . import ionitof_url

log = logging.getLogger()


class SSEventListener(Iterable):

    def __init__(self, endpoint=''):
        if not endpoint:
            endpoint = ionitof_url + '/api/timing/stream'
        self.endpoint = endpoint
        self._response = None
        self.stream = None
        self.subscriptions = []

    def subscribe(self, event='cycle'):
        if self.stream is None:
            r = requests.get(self.endpoint, stream=True)
            if not r.ok:
                log.error(f"no connection to {self.endpoint} (got [{r.status_code}])")
                r.raise_for_status()

            self._response = r
            self.stream = r.iter_lines()

        self.subscriptions.append(event)

    def unsubscribe(self, event='cycle'):
        self.subscriptions.remove(event)
        if not len(self.subscriptions):
            log.debug(f"closing connection to {self.endpoint}")
            self._response.close()
            self.stream = None

    def __iter__(self):
        if self.stream is None:
            raise Exception("call .subscribe() first to listen for events")

        while True:
            line = next(self.stream)  # blocks...
            if not line:
                continue

            line = line.decode('latin-1')
            key, msg = line.split(':', maxsplit=1)
            msg = msg.strip()
            if key == 'event':
                self.event = msg
                if msg not in self.subscriptions:
                    log.debug(f"skipping event <{msg}>")
                    continue

            elif key == 'data':
                yield msg

            else:
                log.warning(f"skipping unknown key <{key}> in stream")
                continue



from collections.abc import Iterable
import logging

log = logging.getLogger()

import requests

from . import ionitof_url


class SSEventListener(Iterable):

    def __init__(self, endpoint=''):
        if not endpoint:
            endpoint = ionitof_url + '/api/timing/stream'
        self.endpoint = endpoint
        self._response = None
        self.stream = None
        self.subscriptions = []

    def subscribe(event='cycle'):
        if self._response is None:
            r = requests.get(endpoint, stream=True)
            if not r.status_ok:
                log.error(f"no connection to {self.endpoint} (got [{r.status_code}])")
            r.raise_for_status()

            self.stream = r.iter_content()
            self._response = r

        self.subscriptions.append(event)

    def unsubscribe(event='cycle'):
        self.subscriptions.remove(event)
        if not len(self.subscriptions):
            log.debug(f"closing connection to {self.endpoint}")
            self._response.close()

    def __iter__(self):
        if self.stream is None:
            raise Exception("call .subscribe() first to listen for events")

        while True:
            line = self.stream.readline()  # blocks...
            if not line:
                continue

            key, msg = line.split(':')
            msg = msg.strip()
            if key == 'event' and msg not in self.subscriptions:
                log.debug(f"skipping event <{msg}>")
                continue

            yield msg



import time

from .base import BaseProcess
from .ioniclient import IoniClient


class WebAPIProcess(BaseProcess):

    @staticmethod
    def make(filename, host='localhost', port=8002):
        '''Factory function.
        '''
        client = IoniClient(host, port)
        return WebAPIProcess(client)

    def __init__(self, filename, client):
        BaseProcess.__init__(self, filename)
        self._client = client

    def __iter__(self):
        return PollingIterator(self._client)


class PollingIterator:

    def __init__(self, client):
        self.client = client

    def __iter__(self):
        return self

    def __next__(self):
        if not self.client.measuring:
            raise StopIteration

        time.sleep(1)
        return self.client



from .datasource import DataSource


class WebAPISource(DataSource):

    def __init__(self, url):
        self.client = IoniClient(host=url)

    def find(self, needle):
        self.client.get_traces()

    def iterrows(self):
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


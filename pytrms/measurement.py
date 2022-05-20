import os
import time

from .sources.h5source import H5Source
from .sources.webapisource import WebAPISource

from .abstract.traceable import Traceable


class Measurement:
    '''
    Base class for PTRMS measurements or batch processing.

    Subclasses of `Process` must implement the `__iter__()` function to guarantee
    the common behaviour for online and offline processing with one or multiple
    datafiles.
    '''
    filename_format = "Cal_%Y-%m-%d_%H-%M-%S"

    @staticmethod
    def _name_convention(fmt, filecount):
        '''Factory for the current filename.

        Gets the `filename_format` string and the current `filecount` as parameters.
        '''
        return time.strftime(fmt, time.localtime())

    @staticmethod
    def make_with_client(host='localhost', port=8002):
        '''Factory function.
        '''
        client = IoniClient(host, port)
        return self.__init__('', client)

    def __init__(self, path, client=None):
        '''Get a file path or directory.
        '''
        if not len(path):
            path = os.getcwd()
        self._dir = os.path.abspath(os.path.dirname(path))
        self._filename = os.path.basename(path)  # may be empty
        self._filecount = 0
        self._dfiles = []
        os.makedirs(self._dir, exist_ok=True)

        self._client = client

    def add_file(path):
        self.sources = sorted(self.sources + [H5Source(path)], key=attrgetter('timezero'))


    @property
    def filename(self):
        basename = self._name_convention(self.filename_format, self._filecount)
        basename += '.h5'
        return os.path.join(self._dir, basename)

    def __iter__(self):
        return iter(self._dfiles)

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


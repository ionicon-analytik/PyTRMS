import os
import time

#from .abstract.traceable import Traceable


class Measurement:
    '''
    Base class for PTRMS measurements or batch processing.

    Subclasses of `Process` must implement the `__iter__()` function to guarantee
    the common behaviour for online and offline processing with one or multiple
    datafiles.
    '''
    filename_format = "Cal_%Y-%m-%d_%H-%M-%S"

    @staticmethod
    def _name_convention(fmt):
        '''Factory for the next filename.

        Gets the `filename_format` string and the current `filecount` as parameters.
        '''
        return time.strftime(fmt, time.localtime())

    @property
    def next_filename(self):
        basename = self._name_convention(self.filename_format)
        basename += '.h5'
        return os.path.join(self.home, basename)

    @property
    def is_running(self):
        if client is None:
            return False

        return True  # TODO :: status abfragen!! (Kandidat: )
        self.client.get('ACQ_SRV_CurrentState')

    def __init__(self, path, client=None):
        '''Get a file path or directory.
        '''
        if not len(path):
            path = os.getcwd()
        self.home = os.path.abspath(os.path.dirname(path))
        os.makedirs(self.home, exist_ok=True)
        self.client = client
        self.datafiles = []
        self.settings = {}
#         self._previous_settings = {}  # TODO : memorize old context

    def start():
        if client is None:
            raise Exception('no connection to instrument')

        if len(self.settings):
            self.client.set_many(self.settings)
            print('applied settings')
        self.client.start_measurement(self.next_filename)
        self.datafiles.append(self.next_filename)
        print(f'started measurement at {time.localtime()}')

    def stop():
        if client is None:
            raise Exception('no connection to instrument')

        self.client.stop_measurement()
        print(f'stopped measurement at {time.localtime()}')




    def add_file(path):
        pass
#         self.sources = sorted(self.sources + [H5Source(path)], key=attrgetter('timezero'))


    def find(self, needle):
        self.client.get_traces()

    def iterrows(self):
        return PollingIterator(self.client)


class PollingIterator:  # TODO :: in etwa so, nur anders

    def __init__(self, client):
        self.client = client

    def __iter__(self):
        return self

    def __next__(self):
        if not False: #self.client.measuring:
            raise StopIteration

        time.sleep(1)
        return self.client


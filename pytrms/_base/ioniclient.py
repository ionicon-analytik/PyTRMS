from abc import ABC, abstractmethod

class IoniClientBase(ABC):

    @property
    @abstractmethod
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        pass

    @property
    @abstractmethod
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        pass

    @abstractmethod
    def connect(self, timeout_s):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def start_measurement(self, path=None):
        '''Start a new measurement and block until the change is confirmed.

        If 'path' is not None, write to the given .h5 file.
        '''
        pass

    @abstractmethod
    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement and block until the change is confirmed.

        If 'future_cycle' is not None and in the future, schedule the stop command.
        '''
        pass

    def __init__(self, host, port):
        # Note: circumvent (potentially sluggish) Windows DNS lookup:
        self.host = '127.0.0.1' if host == 'localhost' else str(host)
        self.port = int(port)

    def __repr__(self):
        return f"<{self.__class__.__name__} @ {self.host}[:{self.port}]>"


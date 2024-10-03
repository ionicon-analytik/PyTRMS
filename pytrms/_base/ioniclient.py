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

    def __init__(self, host, port):
        # Note: circumvent (potentially sluggish) Windows DNS lookup:
        self.host = '127.0.0.1' if host == 'localhost' else str(host)
        self.port = int(port)

    def __repr__(self):
        return f"<{self.__class__.__name__} @ {self.host}[:{self.port}]>"


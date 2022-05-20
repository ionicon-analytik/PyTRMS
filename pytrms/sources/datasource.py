import os
import time
from abc import ABCMeta, abstractmethod


class DataSource(metaclass=ABCMeta):
    '''Base class for offline and online data sources.
    '''

    @abstractmethod
    def find(self, needle):
        '''Find traces by name (e.g. 'H2o_max', 'Valve_42', ...) or by closest exact mass.
        '''
        raise NotImplementedError
    
    @abstractmethod
    def iterrows(self):
        '''Iterates over points in time and returns each as a Pandas.Series object.
        '''
        raise NotImplementedError


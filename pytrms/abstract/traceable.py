import os
import time
from abc import ABCMeta, abstractmethod


class Traceable(metaclass=ABCMeta):
    '''Basic functionality for handling traces.

    What is `Traceable` can be iterated over like a `Pandas.DataFrame` and
    is able to find a trace by name or exact mass.
    '''

    @abstractmethod
    def find(self, needle):
        '''Find a trace by name (e.g. 'H2o_max', 'Valve_42') or by closest exact mass.

        Returns a `Pandas.Series` object.
        '''
        raise NotImplementedError
    
    @abstractmethod
    def iterrows(self):
        '''Iterates over points in time and returns each as a `Pandas.Series` object.
        '''
        raise NotImplementedError


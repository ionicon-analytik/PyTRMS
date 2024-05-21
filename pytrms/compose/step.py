import sys
import json


class Step:
    '''A serializable definition for a Step or an Action.

    When defining a Step with start-delay, the 'AUTO_UseMean' flag will
    be automatically appended:
    >>> step = Step("H50", {'DPS_Udrift': 500}, 10, start_delay=2)
    >>> step.set_values
    {'DPS_Udrift': 500}

    Note, that no Automation-numbers can be defined in the step:
    >>> Step("H50", {'AUTO_UseMean': 0}, 10, start_delay=2)
    Traceback (most recent call last):
      ...
    Exception: Automation numbers cannot be defined

    '''

    protected_keys = ['AME_RunNumber', 'AME_StepNumber', 'AUTO_UseMean'] 
    
    def __init__(self, name, set_values, duration, start_delay):
        self.name = str(name)
        self.set_values = dict(set_values)
        self.duration = int(duration)
        self.start_delay = int(start_delay)

        assert len(self.name) > 0
        assert self.duration >= 0
        assert self.start_delay >= 0
        assert self.start_delay < self.duration

        for key in self.set_values.keys():
            assert key not in Step.protected_keys, "Automation numbers cannot be defined"


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=False, optionflags=doctest.ELLIPSIS)


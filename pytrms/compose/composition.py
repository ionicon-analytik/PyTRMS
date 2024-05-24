import sys
import json
import itertools
import logging
from collections.abc import Iterable
from collections import namedtuple
from functools import wraps

__all__ = ['Step', 'Composition']

log = logging.getLogger()


def coroutine(func):
    @wraps(func)
    def primer(*args, **kwargs):
        coro = func(*args, **kwargs)
        next(coro)
        return coro
    return primer



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
    AssertionError: Automation numbers cannot be defined

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


class Composition(Iterable):
    '''Provides a (possibly infinite) iterable that yields a sequence of Steps.

    This will repeat the same step for all eternity...
    >>> co = Composition([Step("H50", {'DPS_Udrift': 500}, 10, 2)])
    >>> co.is_finite
    False

    ...while this Composition will take two steps and exit...
    >>> co = Composition([
    ...         Step("Oans", {"Eins": 1}, 10, start_delay=2),
    ...         Step("Zwoa", {"Zwei": 2}, 10, start_delay=3)
    ...      ],
    ...      max_runs=1,
    ...      start_cycle=8)
    >>> co.is_finite
    True

    ...without automation (default)...
    >>> list(co.sequence())
    [(8, {'Eins': 1}), (18, {'Zwei': 2})]
    
    ...with an action-number at the start...
    >>> co.start_action = 7
    >>> list(co.sequence())
    [(8, {'AME_ActionNumber': 7}), (8, {'Eins': 1}), (18, {'Zwei': 2})]

    ...or with automation numbers, where the 'start_delay' comes into play:
    >>> co.generate_automation = True
    >>> list(co.sequence())
    [(8, {'AME_ActionNumber': 7}), (8, {'Eins': 1, 'AME_StepNumber': 1, 'AME_RunNumber': 1}), (8, {'AUTO_UseMean': 0}), (10, {'AUTO_UseMean': 1}), (18, {'Zwei': 2, 'AME_StepNumber': 2}), (18, {'AUTO_UseMean': 0}), (21, {'AUTO_UseMean': 1})]
    
    '''

    STEP_MARKER    = 'AME_StepNumber'
    RUN_MARKER     = 'AME_RunNumber'
    USE_MARKER     = 'AUTO_UseMean'
    ACTION_MARKER  = 'AME_ActionNumber'
    
    @staticmethod
    def load(filename, **kwargs):
        with open(filename, 'r') as ifstream:
            steps = list(json.load(ifstream))
            return Composition(steps, **kwargs)

    def __init__(self, steps, max_runs=-1, start_cycle=0, start_action=None, generate_automation=False, foresight_runs=5, schedule_delay=5):
        self.steps = [Step(**item) if isinstance(item, dict) else item for item in steps]
        self.max_runs            = int(max_runs)
        self.start_cycle         = int(start_cycle)
        self.start_action        = int(start_action) if start_action is not None else None
        self.generate_automation = bool(generate_automation)
        self.foresight_runs      = int(foresight_runs) if self.max_runs < 0 else max(int(foresight_runs), self.max_runs)
        self.schedule_delay      = int(schedule_delay)
        
        assert len(self.steps) > 0, "empty step list"
        assert self.max_runs != 0, "max_runs cannot be zero"
        assert self.foresight_runs > 0, "foresight_runs must be positive"
        assert self.schedule_delay > 0, "schedule_delay must be positive"
        names = set(step.name for step in self.steps)
        assert len(names) == len(self.steps), "duplicate step name"

    @property
    def is_finite(self):
        '''whether or not the iteration of steps will ever finish.'''
        return self.max_runs > 0

    def dump(self, ofstream):
        json.dump(self, ofstream, indent=2, default=vars)

    def sequence(self):
        '''A (possibly infinite) iterator over this Composition's future_cycles and steps.

        Note, that this will insert "fake" steps to account for start-delays!

        The first 'future_cycle' is 0 unless otherwise specified with class-parameter 'start_cycle'.
        This generates AME_Run/Step-Number and AUTO_UseMean unless otherwise specified.
        '''
        future_cycle = self.start_cycle
        if self.start_action is not None:
            yield future_cycle, dict([(self.ACTION_MARKER, int(self.start_action))])
        
        for run, step, current in self:
            automation = {self.STEP_MARKER: step}
            if step == 1:
                automation[self.RUN_MARKER] = run

            set_values = dict(current.set_values)
            if self.generate_automation:
                set_values = dict(**set_values, **automation)

            yield future_cycle, set_values

            # insert two updates for AUTO_UseMean flag:
            if self.generate_automation and current.start_delay > 0:
                yield future_cycle, {self.USE_MARKER: 0}
                yield future_cycle + current.start_delay, {self.USE_MARKER: 1}

            future_cycle = future_cycle + current.duration

    @coroutine
    def schedule_routine(self, schedule_fun):
        '''Create a coroutine that receives the current cycle and yields the last scheduled cycle.
        
        'schedule_fun' should be a callable taking three arguments '(parID, value, schedule_cycle)'
        
        >>> co = Composition([
        ...         Step("Oans", {"Eins": 1}, 10, start_delay=2),
        ...         Step("Zwoa", {"Zwei": 2}, 10, start_delay=3)
        ...      ],
        ...      foresight_runs=2,
        ...      schedule_delay=6)
        >>> coro = co.schedule_routine(print)
        >>> wake_cycle = coro.send(1)  # yields at least 'foresight_runs'
        Eins 1 0
        Zwei 2 10
        Eins 1 20
        Zwei 2 30
        Eins 1 40
        
        >>> wake_cycle  # prints 50 - 'schedule_delay'
        44
        
        '''
        # feed all future updates for a given current cycle to the Dirigent
        log.debug("schedule_routine: initializing...")
        sequence = self.sequence()
        foresight_cycles = self.foresight_runs * sum(step.duration for step in self.steps)
        next_cycle, set_values = next(sequence)
        while True:
            # receive current cycle, yield proposed wake cycle...
            current_cycle = yield next_cycle - self.schedule_delay
            log.debug(f"schedule_routine: got [{current_cycle}]")
            while next_cycle < current_cycle + foresight_cycles:
                log.debug(f'scheduling cycle [{next_cycle}] ~> {set_values}')
                for parID, value in set_values.items():
                    schedule_fun(parID, value, next_cycle)
                next_cycle, set_values = next(sequence)

    def __iter__(self):
        rv = namedtuple('sequence_info', ['step', 'run', 'step_info'])
        for run in itertools.count(1):
            if run > self.max_runs > 0:
                break

            for step, step_info in enumerate(self.steps, start=1):
                yield rv(run, step, step_info)


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=False, optionflags=doctest.ELLIPSIS)


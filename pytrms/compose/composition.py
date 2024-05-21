import sys
import json
import itertools
from collections.abc import Iterable
from collections import namedtuple

from .step import Step


class Composition(Iterable):
    '''Provides a (possibly infinite) iterable that yields a sequence of Steps.

    This will repeat the same step for all eternity...
    >>> co = Composition([Step("H50", {'DPS_Udrift': 500}, 10, 2)])
    >>> co.is_finite
    False

    ...while this Composition will take two steps and exit...
    >>> co = Composition([
    ...         Step("Oans", {}, 10, start_delay=2),
    ...         Step("Zwoa", {}, 10, start_delay=3)
    ...      ],
    ...      max_runs=1)
    >>> co.is_finite
    True

    ...were it not for the start-delay that produces intermediate steps:
    >>> list(co.sequence(start_cycle=8))
    [(8, <__main__.Step ...>), (10, <__main__.Step ...>), (18, <__main__.Step ...>), (21, <__main__.Step ...>)]

    '''

    STEP_MARKER = 'AME_StepNumber'
    RUN_MARKER = 'AME_RunNumber'
    USE_MARKER = 'AUTO_UseMean'
    
    @staticmethod
    def load(fstream, **kwargs):
        steps = list(json.load(fstream))
        return Composition(steps, **kwargs)

    def __init__(self, steps, max_runs=-1, start_cycle=0, generate_automation=True):
        self.steps = [Step(**item) if isinstance(item, dict) else item for item in steps]
        self.max_runs = int(max_runs)
        self.start_cycle = start_cycle
        self.generate_automation = generate_automation

        assert len(self.steps) > 0, "empty step list"
        names = set(step.name for step in self.steps)
        assert len(names) == len(self.steps), "duplicate step name"

    @property
    def is_finite(self):
        '''whether or not the iteration of steps will ever finish.'''
        return self.max_runs > 0

    def dump(self, fstream=sys.stdout):
        json.dump(self, fstream, indent=2, default=vars)

    def sequence(self):
        '''A (possibly infinite) iterator over this Composition's future_cycles and steps.

        Note, that this will insert "fake" steps to account for start-delays!

        The first 'future_cycle' is 0 unless otherwise specified.
        This generates AME_Run/Step-Number and AUTO_UseMean unless otherwise specified.
        '''
        future_cycle = self.start_cycle
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


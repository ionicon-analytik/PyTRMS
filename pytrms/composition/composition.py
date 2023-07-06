import sys
import json
from collections import namedtuple

from .step import Step


class Composition:
    '''Provides a (possibly infinite) iterable that yields a sequence of Steps.

    This will repeat the same step for all eternity...
    >>> co = Composition([Step("H50", {'DPS_Udrift': 500}, 10, 2, post_step="H50")], start_step="H50")
    >>> co.is_finite()
    False

    ...while this Composition has a Step that's never reached...
    >>> co = Composition([
    ...         Step("Oans", {}, 10, 2, post_step="Zwoa"),
    ...         Step("null", {}, 10, 2, post_step="Zwoa"),
    ...         Step("Zwoa", {}, 10, 2, post_step=None)
    ...     ], start_step="Oans")
    Traceback (most recent call last):
        ...
    AssertionError: not all steps are executed

    ...while this Composition will take two steps and exit...
    >>> co = Composition([
    ...         Step("Oans", {}, 10, start_delay=2, post_step="Zwoa"),
    ...         Step("Zwoa", {}, 10, start_delay=3, post_step=None)
    ...     ], start_step="Oans")
    >>> co.is_finite()
    True

    ...were it not for the start-delay that produces intermediate steps:
    >>> list(co.play(start_cycle=8))
    [(8, <__main__.Step ...>), (10, <__main__.Step ...>), (18, <__main__.Step ...>), (21, <__main__.Step ...>)]

    '''

    STEP_MARKER = 'AME_StepNumber'
    RUN_MARKER = 'AME_RunNumber'
    USE_MARKER = 'AUTO_UseMean'
    
    @staticmethod
    def load(stream):
        return Composition(**json.load(stream))

    @property
    def _lut(self):
        return dict((step.name, step) for step in self.steps)

    def __init__(self, steps, start_step):
        self.start_step = start_step
        self.steps = [Step(**item) if isinstance(item, dict) else item for item in steps]

        assert self.start_step is not None, "start_step can not be None"
        assert len(self._lut) == len(self.steps), "duplicate step name"
        assert self.start_step in self._lut, "missing start_step in steps"
        assert all(step.post_step in self._lut or step.post_step is None
                for step in self.steps), "post_step w/o definition"

        if self.is_finite():
            assert len(self.steps) == len(self), "not all steps are executed"

    def is_finite(self):
        '''whether or not the iteration of steps will ever finish.'''
        start_step_repeats = any(step.post_step == self.start_step for step in self.steps)
        return not start_step_repeats

    def __len__(self):
        if not self.is_finite():
            raise RecursionError()

        def following(step):
            if step is None:
                return 0
            return 1 + following(self._lut.get(step.post_step))

        return following(self._lut.get(self.start_step))

    def dump(self, stream=sys.stdout):
        json.dump(self, stream, indent=2, default=vars)

    def play(self, start_cycle=0, generate_automation=True):
        '''A (possibly infinite) iterator over this Composition's future_cycles and steps.

        Note, that this will insert "fake" steps to account for start-delays!

        The first 'future_cycle' is 0 unless otherwise specified.
        This generates AME_Run/Step-Number and AUTO_UseMean unless otherwise specified.
        '''
        future_cycle = start_cycle
        current = self._lut[self.start_step]
        run = step = 0

        while current is not None:
            step = step % len(self.steps) + 1
            automation = {self.STEP_MARKER: step}
            if current.name == self.start_step:
                run += 1
                automation[self.RUN_MARKER] = run

            updates = dict(current.set_values)
            if generate_automation:
                updates = dict(**updates, **automation)

            yield future_cycle, updates
            # insert two updates for AUTO_UseMean flag:
            if generate_automation and current.start_delay > 0:
                yield future_cycle, {self.USE_MARKER: 0}
                yield future_cycle + current.start_delay, {self.USE_MARKER: 1}

            future_cycle = future_cycle + current.duration
            current = self._lut.get(current.post_step, None)


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=False, optionflags=doctest.ELLIPSIS)


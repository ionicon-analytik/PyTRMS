import sys
import json
import itertools
import logging
from collections.abc import Iterable
from collections import namedtuple
from itertools import tee
from functools import wraps

__all__ = ['Step', 'Composition']

log = logging.getLogger(__name__)


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

    Note, that no Automation-numbers can be defined in the step..
    >>> Step("H50", {'AUTO_UseMean': 0}, 10, start_delay=2)
    Traceback (most recent call last):
      ...
    AssertionError: a Step must not define AME-numbers

    ..and neither can a 'OP_Mode' alongside anything else:
    >>> Step("Odd2", {'DPS_Udrift': 345, 'OP_Mode': 2}, 10, start_delay=2)
    Traceback (most recent call last):
      ...
    AssertionError: if Step defines 'OP_Mode', nothing else can be!

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

        for key in self.set_values:
            assert key not in Step.protected_keys, "a Step must not define AME-numbers"
        if 'OP_Mode' in self.set_values:
            assert len(self.set_values) == 1, "if Step defines 'OP_Mode', nothing else can be!"

    def __repr__(self):
        return f"{self.name}: ({self.start_delay}/{self.duration}) sec ~> {self.set_values}"


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

    ...with an action-number at the start (note, that AME-numbers are 1 cycle ahead)...
    >>> co.start_action = 7
    >>> list(co.sequence())
    [(9, {'AME_ActionNumber': 7}), (8, {'Eins': 1}), (18, {'Zwei': 2})]

    ...or with automation numbers, where the 'start_delay' comes into play:
    >>> co.generate_automation = True
    >>> seq = co.sequence()
    >>> next(seq)
    (9, {'AME_ActionNumber': 7})

    >>> next(seq)
    (8, {'Eins': 1})

    >>> next(seq)
    (9, {'AME_StepNumber': 1, 'AME_RunNumber': 1, 'AUTO_UseMean': 0})

    >>> next(seq)
    (11, {'AUTO_UseMean': 1})

    >>> next(seq)
    (18, {'Zwei': 2})

    >>> next(seq)
    (19, {'AME_StepNumber': 2, 'AUTO_UseMean': 0})

    >>> next(seq)
    (22, {'AUTO_UseMean': 1})

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

    def __init__(self, steps, max_runs=-1, start_cycle=0, start_action=None, generate_automation=False, foresight_runs=5):
        self.steps = [Step(**item) if isinstance(item, dict) else item for item in steps]
        self.max_runs            = int(max_runs)
        self.start_cycle         = int(start_cycle)
        self.start_action        = int(start_action) if start_action is not None else None
        self.generate_automation = bool(generate_automation)
        self.foresight_runs      = int(foresight_runs) if self.max_runs < 0 else max(int(foresight_runs), self.max_runs)

        assert len(self.steps) > 0, "empty step list"
        assert self.max_runs != 0, "max_runs cannot be zero"
        assert self.foresight_runs > 0, "foresight_runs must be positive"
        names = set(step.name for step in self.steps)
        assert len(names) == len(self.steps), "duplicate step name"

    @property
    def is_finite(self):
        '''whether or not the iteration of steps will ever finish.'''
        return self.max_runs > 0

    def dump(self, ofstream):
        json.dump(self.steps, ofstream, indent=2, default=vars)

    def translate_op_modes(self, preset_items, check=True):
        '''Given the `preset_items` (from a presets-file), compile a list of set_values.

        >>> presets = {}
        >>> presets[0] = ('H3O+', {('Drift', 'Global_System.DriftPressureSet', 'FLOAT'): 2.6})
        >>> presets[2] = ('O3+', {('T-Drift[°C]', 'Global_Temperatures.TempsSet[0]', 'FLOAT'): 75.0})

        next, define a couple of Steps that use the presets (a.k.a. 'OP_Mode'):
        >>> steps = []
        >>> steps.append(Step('uno', {'OP_Mode': 0}, 10, 2))  # set p-Drift by OP_Mode
        >>> steps.append(Step('due', {'Udrift': 420.0, 'T-Drift': 81.0}, 10, 2))
        >>> steps.append(Step('tre', {'OP_Mode': 2}, 10, 2))  # set T-Drift by OP_Mode

        the Composition of these steps will translate to the output underneath.
        note, that the set-value for Pdrift_Ctrl is carried along with each step:
        >>> co = Composition(steps)
        >>> co.translate_op_modes(presets, check=False)
        [{'DPS_Pdrift_Ctrl_Val': 2.6}, {'Udrift': 420.0, 'T-Drift': 81.0, 'DPS_Pdrift_Ctrl_Val': 2.6}, {'T-Drift': 75.0, 'DPS_Pdrift_Ctrl_Val': 2.6, 'Udrift': 420.0}]

        Since we didn't specify the full set of reaction-parameters, the self-check will fail:
        >>> co.translate_op_modes(presets, check=True)
        Traceback (most recent call last):
            ...
        AssertionError: reaction-data missing in presets

        '''
        if preset_items is None:
            raise ValueError('preset_items is None')

        # Note: the `preset_items` is a dict[step_index] ~> (name, preset_items)
        #  and in the items one would expect these keys:
        preset_keys = {
            'PrimionIdx':       ('PrimionIdx', '', 'INT'),
            'TransmissionIdx':  ('TransmissionIdx', '', 'INT'),
            'DPS_Udrift':       ('UDrift', 'Global_DTS500.TR_DTS500_Set[0].SetU_Udrift', 'FLOAT'),
            'DPS_Pdrift_Ctrl_Val': ('Drift', 'Global_System.DriftPressureSet', 'FLOAT'),
            'T-Drift':          ('T-Drift[°C]', 'Global_Temperatures.TempsSet[0]', 'FLOAT'),
        }
        # make a deep copy of the `set_values`:
        set_values = [dict(step.set_values) for step in self.steps]
        carry = dict()
        for entry in set_values:
            # replace OP_Mode with the stuff found in preset_items
            if 'OP_Mode' in entry:
                index = entry['OP_Mode']
                name, items = preset_items[index]
                for parID, key in preset_keys.items():
                    if key in items:
                        entry[parID] = items[key]
                del entry['OP_Mode']

            # Note: each preset is only an update of set-values over what has already
            #  been set. thus, when following the sequence of OP_Modes, each one must
            #  carry with it the set-values of all its predecessors:
            carry.update(entry)
            entry.update(carry)
            if check:
                assert all(key in entry for key in preset_keys), "reaction-data missing in presets"

        return set_values

    def sequence(self):
        '''A (possibly infinite) iterator over this Composition's future_cycles and steps.

        Note, that this will insert "fake" steps to account for start-delays!

        The first 'future_cycle' is 0 unless otherwise specified with class-parameter 'start_cycle'.
        This generates AME_Run/Step-Number and AUTO_UseMean unless otherwise specified.
        '''
        _offset_ame = True  # whether ame-numbers should mark the *next* cycle, see [#2897]

        future_cycle = self.start_cycle
        if self.start_action is not None:
            yield future_cycle + int(_offset_ame), dict([(self.ACTION_MARKER, int(self.start_action))])

        for run, step, step_info in self:
            yield future_cycle, dict(step_info.set_values)

            if self.generate_automation:
                automation = {self.STEP_MARKER: step}
                if step == 1:
                    automation[self.RUN_MARKER] = run

                if step_info.start_delay == 0:
                    # all cycles get the AUTO_UseMean flag set to True:
                    automation[self.USE_MARKER] = 1
                    yield future_cycle + int(_offset_ame), automation
                else:
                    # split into two updates for AUTO_UseMean flag:
                    automation[self.USE_MARKER] = 0
                    yield future_cycle + int(_offset_ame), automation
                    yield future_cycle + int(_offset_ame) + step_info.start_delay, {self.USE_MARKER: 1}

            future_cycle = future_cycle + step_info.duration

    @coroutine
    def schedule_routine(self, schedule_fun):
        '''Create a coroutine that receives the current cycle and yields the last scheduled cycle.

        'schedule_fun' should be a callable taking three arguments '(parID, value, schedule_cycle)'

        >>> co = Composition([
        ...         Step("Oans", {"Eins": 1}, 10, start_delay=2),
        ...         Step("Zwoa", {"Zwei": 2}, 10, start_delay=3)
        ...      ],
        ...      foresight_runs=2)
        >>> coro = co.schedule_routine(print)
        >>> wake_cycle = coro.send(1)  # yields at least 'foresight_runs'
        Eins 1 0
        Zwei 2 10
        Eins 1 20
        Zwei 2 30
        Eins 1 40

        >>> wake_cycle  # should wake up in time before the last run has begun..
        30

        '''
        # feed all future updates for a given current cycle to the Dirigent
        log.debug("schedule_routine: initializing...")
        sequence = self.sequence()
        run_duration_cycles = sum(step.duration for step in self.steps)
        foresight_cycles = self.foresight_runs * run_duration_cycles
        next_cycle, set_values = next(sequence)
        while True:
            # receive current cycle, yield proposed wake cycle...
            current_cycle = yield next_cycle - run_duration_cycles * max(self.foresight_runs - 2, 1)
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


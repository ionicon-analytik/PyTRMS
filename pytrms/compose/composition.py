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
    '''A serializable definition for an AME Step.

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

    ...or with automation numbers, where the 'start_delay' comes into play:
    >>> seq = co.sequence(generate_automation=True)
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
    _version = "1.0"

    STEP_MARKER    = 'AME_StepNumber'
    RUN_MARKER     = 'AME_RunNumber'
    USE_MARKER     = 'AUTO_UseMean'

    @staticmethod
    def load(ifstream):
        """helper method for testing and format display.

        >>> from io import StringIO

        VERSION < 1.0 ..................................

        >>> s = StringIO('''
        ... [
        ...   {
        ...     "name": "uno",
        ...     "set_values": {
        ...       "OP_Mode": 1
        ...     },
        ...     "duration": 10,
        ...     "start_delay": 2
        ...   }
        ... ]
        ... ''')
        >>> c = Composition.load(s)
        >>> c.steps
        [uno: (2/10) sec ~> {'OP_Mode': 1}]

        VERSION 1.0 ....................................

        >>> s = StringIO('''
        ... {
        ...   "version": "1.0",
        ...   "steps": [
        ...     {
        ...       "name": "uno",
        ...       "set_values": {
        ...         "OP_Mode": 1
        ...       },
        ...       "duration": 10,
        ...       "start_delay": 2
        ...     }
        ...   ],
        ...   "start_cycle": 7,
        ...   "spec_duration_ms": 123.4
        ... }
        ... ''')
        >>> c = Composition.load(s)
        >>> c.steps
        [uno: (2/10) sec ~> {'OP_Mode': 1}]

        >>> c.start_cycle
        7

        >>> c.spec_duration_ms
        123.4

        VERSION 1.1 ....................................

        >>> s = StringIO('''
        ... {
        ...   "version": "1.1"
        ... }
        ... ''')
        >>> c = Composition.load(s)
        Traceback (most recent call last):
            ...
        NotImplementedError: version = '1.1'

        """
        j = json.load(ifstream)
        # keep backwards compatibility as "0.9":
        version = j["version"] if isinstance(j, dict) else "0.9"

        if version == "0.9":
            steps = list(j)
            return Composition(steps)
        if version == "1.0":
            del j["version"]
            return Composition(**j)

        raise NotImplementedError(f"{version = }")

    def __init__(self, steps, max_runs=-1, start_cycle=0, spec_duration_ms=1000.0):
        self.version = Composition._version
        self.steps = [Step(**item) if isinstance(item, dict) else item for item in steps]
        self.max_runs           = int(max_runs)
        self.start_cycle        = int(start_cycle)
        self.spec_duration_ms   = float(spec_duration_ms)

        assert len(self.steps) > 0, "empty step list"
        assert self.max_runs != 0, "max_runs cannot be zero"
        names = set(step.name for step in self.steps)
        assert len(names) == len(self.steps), "duplicate step name"

    @property
    def is_finite(self):
        '''whether or not the iteration of steps will ever finish.'''
        return self.max_runs > 0

    @property
    def run_duration_cycles(self):
        '''the duration in cycles of each cyclic AME run.'''
        return sum(step.duration for step in self.steps)

    def dump(self, ofstream):
        '''Write this configuration into a open file object.

        >>> c = Composition([Step('uno', {'OP_Mode': 1}, 10, 2)])
        >>> from io import StringIO
        >>> s = StringIO()
        >>> c.dump(s)
        >>> s.seek(0)
        0

        >>> print(s.read())
        {
          "version": "1.0",
          "steps": [
            {
              "name": "uno",
              "set_values": {
                "OP_Mode": 1
              },
              "duration": 10,
              "start_delay": 2
            }
          ],
          "max_runs": -1,
          "start_cycle": 0,
          "spec_duration_ms": 1000.0
        }

        '''
        fmt = {
            "version": self._version,
            "steps": self.steps,
        }
        json.dump(self, ofstream, indent=2, default=vars)

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

    def sequence(self, generate_automation=False):
        '''A (possibly infinite) iterator over this Composition's future_cycles and steps.

        Note, that this will insert "fake" steps to account for start-delays!

        The first 'future_cycle' is 0 unless otherwise specified with class-parameter 'start_cycle'.
        This generates AME_Run/Step-Number and AUTO_UseMean unless otherwise specified.
        '''
        _offset_ame = True  # whether ame-numbers should mark the *next* cycle, see [#2897]

        future_cycle = self.start_cycle
        for run, step, step_info in self:
            yield future_cycle, dict(step_info.set_values)

            if generate_automation:
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
    def schedule_routine(self, *, foresight_runs=3, generate_automation=True):
        '''Create a coroutine that receives the current cycle and yields the last scheduled cycle.

        Example for a Composition with two steps. The initial horizon covers
        the first 2 full runs as specified plus a safety margin:

        >>> co = Composition([
        ...         Step("Oans", {"Eins": 1}, 20, start_delay=2),
        ...         Step("Zwoa", {"Zwei": 2}, 35, start_delay=5)
        ...      ])
        >>> co.run_duration_cycles
        55

        >>> coro = co.schedule_routine(foresight_runs=2, generate_automation=False)
        >>> batch, wake_cycle = coro.send(0)  # yields at least the two 'foresight_runs':
        >>> batch
        [('Eins', 1, 0), ('Zwei', 2, 20), ('Eins', 1, 55), ('Zwei', 2, 75), ('Eins', 1, 110), ('Zwei', 2, 130)]

        >>> wake_cycle == co.run_duration_cycles * 2  # wake us up when foresight_runs expired:
        True

        An example with only 1 step: Even the low 'foresight_runs=1' produce
        enough information ahead of time (minimum in this case: 40 seconds):

        >>> co = Composition([
        ...         Step("OnlyOne", {"Eins": 1}, 10, start_delay=2),
        ...      ])
        >>> co.run_duration_cycles
        10

        >>> coro = co.schedule_routine(foresight_runs=1, generate_automation=False)
        >>> batch, wake_cycle = coro.send(1)  # yields at least 40 seconds (== cycles):
        >>> batch
        [('Eins', 1, 0), ('Eins', 1, 10), ('Eins', 1, 20), ('Eins', 1, 30), ('Eins', 1, 40), ('Eins', 1, 50)]

        >>> wake_cycle  # the safety margin is much larger than the foresight_runs:
        11

        >>> batch, _ = coro.send(wake_cycle)  # continues the sequence one run at a time...
        >>> batch
        [('Eins', 1, 60)]

        >>> batch, _ = coro.send(wake_cycle)  # ...without repetition...
        >>> batch
        []

        >>> batch, _ = coro.send(42)  # ...but immediately catching up!
        >>> batch
        [('Eins', 1, 70), ('Eins', 1, 80), ('Eins', 1, 90)]

        An finite example that schedules only 2 runs and raises StopIteration:

        >>> co = Composition([
        ...         Step("Oans", {"Eins": 1}, 10, start_delay=2),
        ...         Step("Zwoa", {"Zwei": 2}, 25, start_delay=5)
        ...      ], max_runs=2, start_cycle=5)
        >>> co.run_duration_cycles
        35

        >>> coro = co.schedule_routine(foresight_runs=7, generate_automation=False)
        >>> batch, wake_cycle = coro.send(0)
        >>> batch
        [('Eins', 1, 5), ('Zwei', 2, 15), ('Eins', 1, 40), ('Zwei', 2, 50)]

        >>> wake_cycle
        0

        >>> batch, wake_cycle = coro.send(0)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        StopIteration

        '''
        if not foresight_runs > 0:
            raise ValueError("foresight_runs must be positive")

        ssd_sec = self.spec_duration_ms * 1e-3  # s/ms

        # feed all future updates for a given current cycle to the Dirigent
        log.debug("schedule_routine: initializing...")
        sequence = self.sequence(generate_automation=generate_automation)
        refill_chunk_cycles = foresight_runs * self.run_duration_cycles
        # Note [#3147]: calculate the size of the refill chunk adaptively:
        #  it should guarantee that the number of requested runs is always
        #  in the schedule! also, we use an absolute and relative safety
        #  margin:
        min_foresight_sec = 40
        min_foresight_cyc = 12
        min_relative_margin = refill_chunk_cycles * 0.05
        leeway_cycles = int(max(
            min_foresight_cyc,              # e.g., 12 cycles
            min_foresight_sec / ssd_sec,    # e.g., 40 seconds worth
            min_relative_margin,            # proportional safety, if desired
        ))
        foresight_cycles = refill_chunk_cycles + leeway_cycles
        propose_wakup = leeway_cycles  # wake to keep chunk always filled

        next_cycle, set_values = next(sequence)
        current_cycle = yield None
        while True:
            batch = []
            try:
                while next_cycle < current_cycle + foresight_cycles:
                    log.debug(f'scheduling cycle [{next_cycle}] ~> {set_values}')
                    for parID, value in set_values.items():
                        batch.append((parID, value, next_cycle))
                    next_cycle, set_values = next(sequence)

                wake_cycle = current_cycle + propose_wakup
                current_cycle = yield batch, wake_cycle

            except StopIteration:
                yield batch, current_cycle

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


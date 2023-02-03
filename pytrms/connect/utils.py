"""Module utils.

Miscellaneous utilities.
"""
import sys
import logging
import threading
from collections import deque

import numpy as np

__all__ = ['Validator', 'Value', 'TimeValue', 'StateMachine']

log = logging.getLogger(__name__)

# thread-safety issue:
# concerns: .state, .state.setter, .iter_specdata(), 
# the setter-method may be called from a different thread than that
# using the iterator. this way, both `state.setter` and `state` may 
# be requested literally at the same time!
# scenario:
# 
# User:                         |  PlayerThread:
# You have waited long enough!  |  time's up! get me the next item of the iterator already!
# >> High5.state = 'take'       |  >> if self.state == 'wait': ...
# 
# thing is, the iterator probably wants to be doing his routing
# without having the state changed underneath his butt. 
# WHILE THE ITERATOR IS IN HIS ROUTINE, THE STATE CANNOT CHANGE.
# it may change before or after that. so both the iterator and
# the setter need to respect the global _lock:
_lock = threading.Lock()


class Value:
    def __init__(self, value, unit=''):
        if not unit:
            value, unit = value
        self.value = value
        self.unit = unit

    def __float__(self):
        return float(self.value)


class TimeValue(Value):
    def __init__(self, value, unit=''):
        super().__init__(value, unit)
        self._td = np.timedelta64(int(self.value), self.unit)

    def at(self, unit):
        return self._td / np.timedelta64(1, unit)


class StateMachine:

    def __init__(self, wait_lock=None):
        if wait_lock is None:
            wait_lock = threading.Lock()
        self.wait_lock = wait_lock
        self._action = 'take'
        self._idle = True

    @property
    def state(self):
        # as of this point, we may have to wait 
        # for the setter method to return:
        with _lock:
            if self._idle:
                return 'idle'
            return self._action

    def set_state(self, new: str):
        """Change the current state.

        `new` must be one of 'take', 'wait', 'idle' or 'noidle'.
        """
        # this method has the sole authority to change the `.wait_lock` !!
        if new == self._action or (new == 'idle' and self._idle):
            return

        # shortcuts for safely toggling the .wait_lock:
        wait_lock = lambda : not self.wait_lock.locked() and self.wait_lock.acquire(blocking=False)
        wait_release = lambda : self.wait_lock.locked() and self.wait_lock.release()

        # as of this point, we may have to wait 
        # for the getter method to return:
        with _lock:
            if new == 'idle':
                self._idle = True
                wait_lock()
            elif new == 'noidle':
                self._idle = False
                if self._action == 'take':
                    wait_release()
            elif new == 'wait':
                self._action = new
                wait_lock()
            elif new == 'take':
                self._action = new
                wait_release()
            else:
                raise ValueError("unknown keyword: %s!" % str(new))


class Validator:
    """Collect errors during a check or validation.

    The `Validator` compares to True, if no errors occured.

    Examples:
    >>> valid = Validator()
    >>> bool(valid)
    True
    >>> Uncertainty = 7  # set a flag
    >>> valid.add_error('is this really the right place??', flag=Uncertainty)
    >>> valid.has_occurred(Uncertainty)
    True

    The validator can be tested for truth:
    >>> if not valid: print('something fishy has happened...')
    something fishy has happened...
    >>> valid
    <Validator with (1) error>

    >>> valid.add_error('Houston, we have a problem!', severity='high')
    >>> valid.report()

    # prints:
    [high] Houston, we have a problem!
    is this really the right place??
    ----------------------------
    There were 2 errors during the check (Flags were set)!

    Use a logger to push all errors to a logfile or similar:
    >>> log = print
    >>> for error in valid: log(error)
    [high] Houston, we have a problem!
    is this really the right place??

    """
    fmt = '[%(severity)s] %(msg)s'

    def __init__(self):
        self._errors = []
        self._flags = 0b0

    @property
    def has_errors(self):
        return bool(len(self._errors))

    def has_occurred(self, flag):
        return bool(flag & self._flags)

    def add_error(self, error_message, severity='', flag=0b0):
        if severity:
            self._errors.insert(0, self.fmt % dict(severity=severity, msg=error_message))
        else:
            self._errors.append(error_message)
        self._flags |= flag

    def report(self, stream=sys.stdout):  # pragma: nocover
        if self.has_errors:
            report = '\n'.join(self._errors)
            report += '\n----------------------------\n'
            if self._flags:
                suffix = ' (Flags were set)!'
            else:
                suffix = '!'
            if len(self._errors) == 1:
                report += 'There was 1 error during the check%s' % suffix
            else:
                report += 'There were %d errors during the check%s' % (len(self._errors), suffix)
        else:
            report= 'All checks passed. '

        print(report, file=stream)

    def __len__(self):
        return len(self._errors)

    def __getitem__(self, item):
        return self._errors[item]

    def __repr__(self):
        if self.has_errors:
            return ('<%s with (%d) error%s>'
                    % (self.__class__.__name__, len(self), '' if len(self) == 1 else 's'))
        else:  # pragma: nocover
            return '<%s (passed)>' % self.__class__.__name__

    def __bool__(self):
        return not self.has_errors

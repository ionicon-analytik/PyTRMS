"""Module ionitof.py.

"""
import os
import time
import logging
from datetime import datetime
from collections import namedtuple, defaultdict
from configparser import ConfigParser

from ._base import BaseConnector, _PTR_reaction_params
from .utils import TimeValue, StateMachine

log = logging.getLogger(__name__)

__all__ = ['IoniTOF']


class IoniTOF(StateMachine, BaseConnector):

    _state = namedtuple('IoniTOF', ('MeasureState', 'ServerState', 'ServerAction'))

    # trace indices:
    RAW = 0
    CORR = 1
    CONC = 2

    # iterator configuration:
    cushion_ms = 150
    # decide what to do when the IoniTOF-manager is idle:
    break_on_idle = False

    def __init__(self, icapi_controller, tps_controller, modbus_controller,
                 ionitof_prefs_file, mode_table):
        self.nsv_ctrl = icapi_controller
        self.tps = tps_controller
        self.modbus = modbus_controller
        if self.modbus is None:
            log.warning("Using the Network Shared Variables for fetching PTR Parameters! "
                        "This might cause delays and crashes if simultaneously fetching "
                        "the Spectrum. Consider using the Modbus connection instead.")
        self.ionitof_prefs_file = ionitof_prefs_file
        self.ionitof_cfg = ConfigParser()
        self.ionitof_cfg.optionxform = str
        self.mode_table = mode_table

        StateMachine.__init__(self)
        self._go = True
        self._pause = False
        self._resume = False

    @property
    def connected(self):
        return self.nsv_ctrl.reconnect()

    @property
    def status(self):
        # Note: this has never displayed something other than:
        # IoniTOF(MeasureState='ReadyIdle', ServerState='OK', ServerAction='Idle')
        # Useful in principle, but not really working how it should...
        return self._state(*self.nsv_ctrl.get_status())

    @property
    def tof_settings(self):
        if not self.ionitof_prefs_file or not os.path.exists(self.ionitof_prefs_file):
            return dict()

        with open(self.ionitof_prefs_file, 'r') as f:
            self.ionitof_cfg.read_file(f)

        sec = self.ionitof_cfg['Surface Concept Settings']
        start_delay = sec.getfloat('Start delay (ns)'), 'ns'
        exponent = sec.getint('Binwidth factor')
        binwidth_base = sec.getfloat('HW Binwidth (ps)')
        binwidth = binwidth_base * 2**exponent, 'ps'

        sec = self.ionitof_cfg['LastSettings']
        single_spec_duration = float(sec.get('Single Spec Time (ms)').replace(',', '.')), 'ms'
        # extraction_time = float(sec.get('Extraction Time (ns)').replace(',', '.')), 'ns'
        max_flight_time = float(sec.get('Max Flight Time (ns)').replace(',', '.')), 'ns'

        sec = self.ionitof_cfg['Calibration']
        autocal_period = float(sec.get('AutoPeriod').replace(',', '.')), 's'

        sec = self.ionitof_cfg['Corrections']
        poisson_dead_time = float(sec.get('Time').replace(',', '.')), 'ns'

        rv = {
            'timebin_width': binwidth,
            'single_spec_duration': single_spec_duration,
            'max_flight_time': max_flight_time,
            'start_delay': start_delay,
            'autocal_period': autocal_period,
            'poisson_dead_time': poisson_dead_time,
            # 'extraction_time': extraction_time,
        }

        return rv

    @property
    def ptr_params(self):
        if self.modbus is None:
            # fallback to NetworkSharedVariables..
            return {par.key: (par.actv, par.unit) for par in self.nsv_ctrl.parse_ptr_params()}

        units = defaultdict(lambda : '-', _PTR_reaction_params)
        return {key: (self.modbus.read(key).Act, units[key]) for key in self.modbus.available_keys}

    @property
    def reaction_params(self):
        if self.modbus is None:
            return {par.key: (par.actv, par.unit) for par in self.nsv_ctrl.parse_reaction_params()}

        return {key: (self.modbus.read(key).Act, unit) for key, unit in _PTR_reaction_params.items()}

    @property
    def tps_voltages(self):
        if self.tps is None:
            log.warning("Requesting TOF Parameters failed! It seems, no TwinCat is installed.")
            return defaultdict(lambda x: '??')

        unit = 'V'

        return {key: (value, unit) for key, value in self.tps.act_values().items()}

    @property
    def prim_ions(self):
        log.warning("using a hardcoded default for ion-list!!")
        return ('H3O+ (hum)', 'O2+', 'NO+', 'H3O+', 'all')

    @property
    def n_timebins(self):
        return self.nsv_ctrl.get_timebins()

    @property
    def specdata(self):
        acycle, fcycle, a_ts, rtime, data = self.nsv_ctrl.get_current_spectrum()
        try:
            a_time = datetime.utcfromtimestamp(a_ts)
        except Exception as exc:
            log.error("Could not convert abs. time: <%s>! "
                      "Got %s: %s" % (str(a_ts), type(exc).__name__, str(exc)))
            a_time = datetime.utcnow()

        # namedtuple('AbsoluteCycle', 'FileCycle', 'DateTime', 'RelTime', 'Data')
        return self._specdata_template(acycle, fcycle, a_time, rtime, data)

    def play(self, playback_speed=1):
        self._go = True
        self._pause = False
        #         try:
        #             log.debug("Starting IoniTOF...")
        #             self.nsv_ctrl.start()
        #         except Exception as exc:
        #             log.error("Got %s: %s" % (type(exc).__name__, str(exc)))

    def pause(self):
        self._go = True
        self._pause = True
        #         try:
        #             log.debug("Stopping IoniTOF...")
        #             self.nsv_ctrl.stop()
        #         except Exception as exc:
        #             log.error("Got %s: %s" % (type(exc).__name__, str(exc)))

    def stop(self):
        self._go = False
        self._pause = False
        #         try:
        #             log.debug("Stopping IoniTOF...")
        #             self.nsv_ctrl.stop()
        #         except Exception as exc:
        #             log.error("Got %s: %s" % (type(exc).__name__, str(exc)))

    def resume(self):
        self._resume = True

    def iter_specdata(self, on_mode_mismatch='skip'):
        # This iterator fetches the specdata from the .nsv_ctrl, yields the
        # spectrum and step and then goes to sleep for one 'single-spec-duration'
        # to await the next spectrum.
        break_on_idle = self.break_on_idle
        mode_table = self.mode_table
        prim_ions = self.prim_ions
        period_s = TimeValue(self.tof_settings['single_spec_duration']).at('s')
        cushion_s = self.cushion_ms / 1000
        if cushion_s >= period_s:
            raise ValueError("the single-spec-duration cannot be smaller than "
                             "the cushion: %fs !< %fs!" % (period_s, cushion_s))
        acycle = -1
        skip_next = False

        # we need to get the actual sleep time, which was observed to be
        # longer by multiples of 16ms (this really depends on the OS).
        # one way of doing this is to stop the elapsed time (although we
        # are currently only looking at the absolute timestamp):
        t0 = time.monotonic()
        def elapsed_s():
            """returns the time elapsed since its last call"""
            nonlocal t0
            t1 = time.monotonic()
            t0, dt = t1, t1-t0
            return dt

        def iter_reaction():
            while True:
                yield self.reaction_params

        step_gen = mode_table.iter_rsc(iter_reaction(), prim_ions,
                                       on_mode_mismatch=on_mode_mismatch)
        last_step = None
        while True:
            specdata = self.specdata
            run, step, cycle = next(step_gen)
            if self._pause or skip_next:
                pass

            else:
                # >>>>>>>> identical to high5 >>>>>>>>>>>>>>>>> #
                # the core of this method is the same in both
                # Connectors. I did not yet find a way to factor
                # this out..
                # in an ideal world, the iter-method would return
                # an iterator object, which keeps the state. but
                # there is a major advantage using a genarator
                # instead, namely the `yield` keyword that allows
                # code to be executed AFTER the statement and is
                # therefore ideal for concurrent execution.
                if self._resume:
                    log.info('resume..')
                    self._resume = False
                    self.set_state('take')

                if step < 0:
                    self.set_state('idle')
                else:
                    self.set_state('noidle')

                    if step != last_step:
                        self.set_state('wait')

                    last_step = step
                    yield specdata, step
                # <<<<<<<< identical to high5 <<<<<<<<<<<<<<<<< #

            if not self._go:
                break

            # detect the IDLE state of the IoniTOF-Manager. this should rather
            # be done using `.nsv_ctrl.status`, but that ain't working..
            if break_on_idle and specdata.AbsoluteCycle == acycle:
                log.info("IoniTOF manager has stopped at cycle (%d)." % acycle)
                break

            if specdata.AbsoluteCycle > acycle + 1 and acycle > 0:
                log.warning("Skipped %d cycle(s). Last cycle was (%d)."
                            % (specdata.AbsoluteCycle - (acycle+1), acycle))

            skip_next = bool(specdata.AbsoluteCycle == acycle)

            # keep track of the current *Cycle* to make sure we are synchronous:
            acycle = specdata.AbsoluteCycle

            # make sure, this loop is synchronized with the NSV-server! if the
            # time differential between writing and reading is less than
            # approx. 150 ms, the performance cost caused by pile-up is 
            # significant! this leads to skips and even crashes!
            # 
            # in the following example, the period is 1000 ms and the sleep
            # time, calculated from the receiving of the specdata until the
            # next timestamp plus the cushion is 500 ms:
            #
            #     specdata.DateTime     
            #    /                             don't request here!     
            #                                 /
            # __|\xxxxxx_______________|\xxxxxxx___________________|\xxxxxxx___
            #   0       150  600  650     1000     1150                time / ms
            #   <--------delta----->    <----------period---------->
            #                       \   <cushion>
            #                        received 
            #                |entry <---sleep-->|broadcast<----sleep----->|..
            now = datetime.utcnow()
            delta_s = (now - specdata.DateTime).total_seconds()
            # it may happen that we missed a cycle, so make sure delta_s < period_s:
            delta_s %= period_s
            sleep_s = period_s - delta_s + cushion_s
            if log.level <= logging.DEBUG:
                log.debug("elapsed: %f ms" % (elapsed_s() * 1000))
                log.debug("going to sleep for %f ms..." % (sleep_s * 1000))
            time.sleep(sleep_s)

    @property
    def traces(self):
        acycle, fcycle, atime, rtime, data = self.nsv_ctrl.get_trace_data()

        # deprecated:
        run = 1

        a_time = datetime.utcfromtimestamp(atime)
        raise NotImplementedError('no step in ionitof!')
        return self._trace_template(acycle, fcycle, run, self.step, a_time, rtime, data)

    @property
    def masses(self):
        return self.nsv_ctrl.get_masses()

    def __repr__(self):
        return '<IoniTOF://%s>' % self.nsv_ctrl.ip


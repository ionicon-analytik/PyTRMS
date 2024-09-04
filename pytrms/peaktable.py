"""Module peaktable.py

Defines classes Peak and PeakTable.

A `Peak` is a predefined template and a directive for the peakfitting
algorithm on how to fit peaks in the spectrum.
This class has additional information of the chemical properties
(chemical formula, isotopic_abundance) to be able to group isotopic peaks
of the same compound together and additional factors (k_rate, multiplier)
to convert a signal into a concentration.

The `PeakTable` holds any number of `Peak`-instances. It can be saved
and recovered to and from various formats, including .json and .tsv and
other custom formats.

>>> from io import StringIO
>>> s = StringIO('''
... {
... "version":"1.0",
... "R":3333,
... "peaks":
... [
... {"label":"H3O+",
...  "center":21.0219,
...  "formula":"?",
...  "parent":"?",
...  "isotopic_abundance":0.002,
...  "k_rate":2.10,
...  "multiplier":488
... }
... ]
... }
... ''')
>>> pt = PeakTable._parse_json(s)
>>> pt
<PeakTable (1) [21.0u]>
>>> pt[0]
<Peak [H3O+] @ 21.0219>

Peaks may be modified and the PeakTable exported in the same format:
>>> pt[0].formula = 'H3O'
>>> pt[0].isotopic_abundance = 0.678
>>> s = StringIO()
>>> pt._write_json(s)
>>> s.seek(0)
0
>>> print(s.read())
{
  "version": "1.0",
  "R": 6000,
  "peaks": [
    {
      "center": 21.0219,
      "label": "H3O+",
      "formula": "H3O",
      "parent": "?",
      "isotopic_abundance": 0.678,
      "k_rate": 2.1,
      "multiplier": 488
    }
  ]
}

"""
import os
import csv
import json
import logging
from configparser import ConfigParser
from functools import total_ordering, partial
from collections import defaultdict
import h5py

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

__all__ = ['Peak', 'PeakTable']


@total_ordering
class Peak:
    """Defines a Peak in the Spectrum.

    Each Peak is uniquely defined by its `center` mass.

    The `float()` function may be called on a `Peak` to return its `center`.

    A `label` may be supplied, otherwise it is derived from the center mass.

    If `borders` are passed explicitly, these borders override the automatic
    border detection based on the instrument resolution.

    Other optional attributes that may be saved in the Peak-instance are
    `formula`, `parent` (Peak), `k_rate`, `multiplier`.

    Keyword arguments:

    - `label`:       attach a label to this peak (default: m42.0000 for mass 42)
    - `borders`:     define the borders of this peak (default: m +/- 0.5u)
    - `k_rate`:      specify a k-rate
    - `multiplier`:  specify a multiplier

    """
    _exact_decimals = 4

    def __init__(self, center, label='', formula='', parent=None, borders=(),
                 isotopic_abundance=1.0, k_rate=2.0, multiplier=1.0,
                 resolution=1000, shift=0):
        self.center = round(float(center), ndigits=Peak._exact_decimals)
        if not label:
            label = 'm{:.4f}'.format(self.center)
        self.label = str(label)
        self.formula = formula
        if isinstance(parent, Peak):
            self.parent = str(parent.label)
        elif parent is not None:
            self.parent = str(parent)
        else:
            self.parent = ''
        self._borders = tuple(map(lambda x: round(float(x), ndigits=4), borders))
        self.isotopic_abundance = float(isotopic_abundance)
        self.k_rate = float(k_rate)
        self.multiplier = float(multiplier)
        self.resolution = float(resolution)
        self.shift = float(shift)

    @property
    def is_unitmass(self):
        return self.center == round(self.center)

    @property
    def borders(self):
        if len(self._borders):
            return self._borders
        else:
            return self.center - 0.5, self.center + 0.5

    def __lt__(self, other):
        return self.center < round(float(other), Peak._exact_decimals)

    def __eq__(self, other):
        return self.center == round(float(other), Peak._exact_decimals)

    def __hash__(self):
        return hash(str(self.center))  # + self.label)

    def __float__(self):
        return self.center

    def __repr__(self):
        return '<%s [%s <~ %s] @ %.4f+%.4f>' % (self.__class__.__name__,
                self.label, self.parent, self.center, self.shift)


class PeakTable:
    """Keeps a list of peaks. Can be merged with other PeakTables by simple addition.

    Supports import/export to various LabView formats.
    """

    @staticmethod
    def from_file(filename):
        base, ext = os.path.splitext(filename)
        if ext == '.ipt':
            with open(filename, 'rb') as f:
                return PeakTable._parse_ipt(f)
        elif ext == '.ipta':
            with open(filename) as f:
                return PeakTable._parse_ipta(f)
        elif ext == '.ipt2':
            with open(filename) as f:
                return PeakTable._parse_ipt2(f)
        elif ext == '.ipt3' or ext == '.json':
            with open(filename) as f:
                return PeakTable._parse_json(f)
        elif ext == '.ionipt':
            with open(filename) as f:
                return PeakTable._parse_ionipt(f)
        elif ext == '.h5':
            with h5py.File(filename, 'r') as f:
                return PeakTable._parse_h5(f)
        else:
            raise ValueError("Can't read from file! Unknown file-extension: '%s'." % ext)

    @staticmethod
    def _parse_ipt(file):
        column_names = ['Descriptions', 'MassCenters', 'BorderLow',
                        'BorderHigh', 'Multipliers', 'kRates']
        table = pd.read_csv(file, sep='\t', skip_blank_lines=True,
                            header=None, names=column_names,
                            index_col=False, float_precision='high')

        peaks = []
        for row in table.itertuples(index=False):
            borders = row.BorderLow, row.BorderHigh
            peaks.append(Peak(center=row.MassCenters, label=row.Descriptions,
                              borders=borders, k_rate=row.kRates,
                              multiplier=row.Multipliers))

        return PeakTable(peaks)

    @staticmethod
    def _parse_ipta(file):
        cp = ConfigParser()
        cp.read_file(file)
        i = 0
        peaks = []
        while True:
            try:
                i += 1
                ps = 'Peak_{:04d}'.format(i)  # the 'peakstring', something like Peak_0042
                sec = cp[ps]
                if int(sec['NumOfPeaks']) > 1:
                    log.warning("File %s contains multipeaks. This feature is not supported "
                                "by this parser! Returning only the first peak!" % file.name)
                borders = float(sec['BorderLow']), float(sec['BorderHigh'])
                peaks.append(Peak(center=float(sec[ps + '_MassCenters_1']),
                                  borders=borders,
                                  label=sec[ps+'_Descriptions_1'],
                                  k_rate=float(sec[ps+'_kRates_1']),
                                  multiplier=float(sec[ps+'_Multipliers_1'])))
            except KeyError:
                break
        log.info("Parsed %d Peaks from %s." % (len(peaks), file.name))

        return PeakTable(peaks)

    @staticmethod
    def _parse_ipt2(file):
        raise NotImplementedError

    @staticmethod
    def _parse_txt(file):
        raise NotImplementedError

    def _parse_h5(file):
        tempData = file['/TRACEdata/TraceInfo']

        # Functions to Convert H5 binary to str, and further to float, int if needed
        vfunc_str = np.vectorize(lambda t: t.decode("utf-8"))
        vfunc_float = np.vectorize(lambda t: float(t.decode("utf-8")))
        vfunc_int = np.vectorize(lambda t: int(t.decode("utf-8")))

        table = pd.DataFrame(data={
            'Descriptions': vfunc_str(tempData[1]),
            'MassCenters': vfunc_float(tempData[2]),
            'BorderLow': vfunc_float(tempData[3]),
            'BorderHigh': vfunc_float(tempData[4]),
            'Multipliers': vfunc_float(tempData[5]),
            'kRates': vfunc_float(tempData[6])},
            index=vfunc_int(tempData[0]))


        peaks = []
        for row in table.itertuples(index=False):
            borders = row.BorderLow, row.BorderHigh
            peaks.append(Peak(center=row.MassCenters, label=row.Descriptions,
                              borders=borders, k_rate=row.kRates,
                              multiplier=row.Multipliers))

        return PeakTable(peaks)

    @staticmethod
    def _parse_json(file):
        version, resolution, peak_list = json.load(file).values()
        peaks = []
        for pars in peak_list:
            peaks.append(Peak(**pars))

        return PeakTable(peaks)

    @staticmethod
    def _parse_ionipt(file):
        
        def _make_peak(ioni_p, borders, shift, parent=None):
            return Peak(ioni_p["center"],
                label=ioni_p["name"],
                formula=ioni_p["ionic_isotope"],
                parent=parent,
                borders=borders,
                isotopic_abundance=ioni_p["isotopic_abundance"],
                k_rate=ioni_p["k_rate"],
                multiplier=ioni_p["multiplier"],
                resolution=ioni_p["resolution"],
                shift=shift)

        peak_list = json.load(file)
        peaks = []
        for item in peak_list:
            border_peak = item["border_peak"]
            borders = (item["low"], item["high"])
            shift = item["shift"]
            parent = None
            MODE = int(item["mode"])
            IGNORE    = 0b00
            INTEGRATE = 0b01
            FIT_PEAKS = 0b10
            if bool(MODE == IGNORE):
                continue
            if bool(MODE & INTEGRATE):
                parent = _make_peak(border_peak, borders, shift)
                peaks.append(parent)
            if bool(MODE & FIT_PEAKS):
                for ioni_peak in item["peak"]:
                    if parent is None:
                        # Note: we denote a peak w/ parent as a "fitted" peak..
                        #  as a workaround, use the first as (its own) parent:
                        parent = ioni_peak["name"]
                    peaks.append(_make_peak(ioni_peak, borders, shift, parent))

        return PeakTable(peaks)

    def _write_json(self, fp, resolution=6000, fileversion='1.0'):
        s = json.dumps({'version': fileversion,
                        'R': resolution,
                        'peaks': [{key: val for key, val in vars(peak).items()
                                            if not key.startswith('_')}
                                  for peak in self.peaks],
                        },
                       indent=2)
        fp.write(s)

    def _write_ipt(self, fp, fileversion='1.0'):
        if fileversion not in ['1.0', '1.1']:
            raise NotImplementedError("Can't write .ipt version %s!" % fileversion)

        out = csv.writer(fp, dialect='excel-tab')
        # Note: pretty-print by using extra width of 10 and 12 for numbers and label,
        #  respectively (this might not be standard csv though):
        _number_format = lambda x: '{:>10.4f}'.format(x)
        _string_format = lambda x: '{:<12s}'.format(x)
        for p in self:
            columns = [p.center] + list(p.borders) + [p.multiplier, p.k_rate]
            if float(fileversion) >= 1.1:
                columns += [p.resolution, p.shift]
            out.writerow([_string_format(p.label)] + list(map(_number_format, columns)))

    def _write_ipta(self, fp, fileversion='1.0'):
        if fileversion != '1.0':
            raise NotImplementedError("Can't write .ipta version %s!" % fileversion)

        cp = ConfigParser()
        cp.optionxform = str

        sec_name = 'General'
        cp.add_section(sec_name)
        sec = cp[sec_name]
        sec['PeaksVersion'] = str(fileversion)

        for i, peak in enumerate(self):
            sec_name = 'Peak_{:04d}'.format(i+1)
            cp.add_section(sec_name)
            sec = cp[sec_name]
            sec['Mode'] = '0'
            sec['NumOfPeaks'] = '1'
            borders = peak.borders
            sec['BorderLow'] = str(borders[0])
            sec['BorderHigh'] = str(borders[1])
            sec[sec_name+'_NumDescriptions'] = '1'
            sec[sec_name+'_Descriptions_1'] = str(peak.label)
            sec[sec_name+'_NumMassCenters'] = '1'
            sec[sec_name+'_MassCenters_1'] = str(peak.center)
            sec[sec_name+'_NumMultipliers'] = '1'
            sec[sec_name+'_Multipliers_1'] = str(peak.multiplier)
            sec[sec_name+'_NumkRates'] = '1'
            sec[sec_name+'_kRates_1'] = str(peak.k_rate)
            sec['GaussPercent'] = '0.000000'
            sec['GaussHeight'] = '0.000000'
            sec['GaussWidth'] = '0.002000'
            sec[sec_name+'_NumIsPrimIon'] = '1'
            sec[sec_name+'_IsPrimIon_1'] = '0.000000'
            sec[sec_name+'_NumSigma'] = '1'
            sec[sec_name+'_Sigma_1'] = '0.000000'
            sec['GaussCenter'] = '0.000000'
            sec['FitFunction'] = '0'

        cp.write(fp)
        log.info("Written %d Peaks to %s." % (len(self), fp.name))

    @staticmethod
    def from_masses(exact_masses):
        return PeakTable([Peak(mass) for mass in exact_masses])

    def __init__(self, peaks: list = ()):
        self.peaks = sorted(peaks)

    @property
    def nominal(self):
        peaks = [peak for peak in self.peaks if not peak.parent]
        return PeakTable(peaks)

    @property
    def fitted(self):
        peaks = [peak for peak in self.peaks if peak.parent]
        return PeakTable(peaks)

    @property
    def exact_masses(self):
        return [peak.center for peak in self.peaks]

    @property
    def mass_labels(self):
        return [peak.label for peak in self.peaks]

    def find_by_mass(self, exact_mass):
        """Return the peak at `exact_mass` up to 4 decimal digits precision.

        Raises KeyError if not found.
        """
        lo, hi = 0, len(self) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self[mid] == exact_mass:
                return self[mid]
            elif self[mid] < exact_mass:
                lo = mid + 1
            elif self[mid] > exact_mass:
                hi = mid - 1

        raise KeyError("No such peak at %s!" % str(exact_mass))

    def group(self):
        groups = defaultdict(list)
        for peak in self:
            groups[peak.parent].append(peak)

        return groups

    def save(self, filename):
        base, ext = os.path.splitext(filename)
        if ext == '.json':
            writer = partial(self._write_json, resolution=6000, fileversion='1.0')
        elif ext == '.ipt3':
            writer = partial(self._write_json, resolution=6000, fileversion='1.0')
        elif ext == '.ipt':
            writer = partial(self._write_ipt, fileversion='1.0')
        elif ext == '.ipta':
            writer = partial(self._write_ipta, fileversion='1.0')
        else:
            raise NotImplementedError("can't export with file extension <%s>!" % ext)

        with open(filename, 'w') as f:
            writer(f)

    def __len__(self):
        return len(self.peaks)

    def __getitem__(self, index):
        return self.peaks[index]

    def __setitem__(self, index, peak):
        if not isinstance(peak, Peak):
            raise TypeError("Can only insert a Peak into a PeakTable!")

        if peak in (self.peaks[:index] + self.peaks[index+1:]):
            raise ValueError("PeakTable must be unique! Can't add %r." % peak)

        self.peaks[index] = peak

    def __add__(self, other):
        if isinstance(other, PeakTable):
            return PeakTable(set(self.peaks) | set(other.peaks))
        elif isinstance(other, Peak):
            return PeakTable(set(self.peaks) | set([other,]))
        else:
            raise TypeError(str(other))

    def __sub__(self, other):
        if isinstance(other, PeakTable):
            return PeakTable(set(self.peaks) ^ set(other.peaks))
        elif isinstance(other, Peak):
            return PeakTable(set(self.peaks) ^ set([other,]))
        else:
            raise TypeError(str(other))

    def __gt__(self, other):
        return PeakTable([peak for peak in self.peaks if peak > other])

    def __ge__(self, other):
        return PeakTable([peak for peak in self.peaks if peak >= other])

    def __lt__(self, other):
        return PeakTable([peak for peak in self.peaks if peak < other])

    def __le__(self, other):
        return PeakTable([peak for peak in self.peaks if peak <= other])

    def __repr__(self):
        if not len(self):
            return '<%s (%d) []>' % (self.__class__.__name__, len(self))
        elif len(self) == 1:
            return '<%s (%d) [%.1fu]>' % (self.__class__.__name__, len(self),
                                          self.peaks[0].center)
        else:
            return '<%s (%d) [%.1fu .. %.1fu]>' % (self.__class__.__name__, len(self),
                                          self.peaks[0].center, self.peaks[-1].center)


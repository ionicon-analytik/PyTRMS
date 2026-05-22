"""@file helpers.py

common helper functions.
"""

def convert_labview_to_posix(lv_time_utc, utc_offset_sec):
    '''Create a `pandas.Timestamp` from LabView time.'''
    from pandas import Timestamp

    # change epoch from 01.01.1904 to 01.01.1970:
    posix_time = lv_time_utc - 2082844800
    # the tz must be specified in isoformat like '+02:30'..
    tz_sec = int(utc_offset_sec)
    tz_designator = '{0}{1:02d}:{2:02d}'.format(
            '+' if tz_sec >= 0 else '-', tz_sec // 3600, tz_sec % 3600 // 60)

    return Timestamp(posix_time, unit='s', tz=tz_designator)


def parse_presets_file(presets_file):
    '''Load a `presets_file` as XML-tree and interpret the "OP_Mode" of this `Composition`.

    The tricky thing is, that any OP_Mode may or may not override previous settings!
    Therefore, it depends on the order of modes in this Composition to be able to assign
    each OP_Mode its actual dictionary of set_values.

    Note, that the preset file uses its own naming convention that cannot neccessarily be
    translated into standard parID-names. You may choose whatever you like to do with it.
    '''
    import xml.etree.ElementTree as ET
    from collections import namedtuple, defaultdict

    _key = namedtuple('preset_item', ['name', 'ads_path', 'dtype'])
    _parse_value = {
        "FLOAT": float,
        "BOOL":  bool,
        "BYTE":  int,
        "ENUM":  int,
    }
    tree = ET.parse(presets_file)
    root = tree.getroot()

    preset_names = {}
    preset_items = defaultdict(dict)
    for index, preset in enumerate(root.iterfind('preset')):
        preset_names[index] = preset.find('name').text.strip()

        if preset.find('WritePrimIon').text.upper() == "TRUE":
            val = preset.find('IndexPrimIon').text
            preset_items[index][_key('PrimionIdx', '', 'INT')] = int(val)

        if preset.find('WriteTransmission').text.upper() == "TRUE":
            val = preset.find('IndexTransmission').text
            preset_items[index][_key('TransmissionIdx', '', 'INT')] = int(val)

        for item in preset.iterfind('item'):
            if item.find('Write').text.upper() == "TRUE":
            #   device_index = item.find('DeviceIndex').text
                ads_path     = item.find('AdsPath').text
                data_type    = item.find('DataType').text
            #   page_name    = item.find('PageName').text
                name         = item.find('Name').text
                value_text   = item.find('Value').text

                key = _key(name, ads_path, data_type)
                val = _parse_value[data_type](value_text)
                preset_items[index][key] = val

    return {index: (preset_names[index], preset_items[index]) for index in preset_names.keys()}


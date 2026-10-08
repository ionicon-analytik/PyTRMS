from pytrms.helpers import parse_presets_directory


def test_parse_presets_directory(tmp_path):
    (tmp_path / '01_N2x.csv').write_text(
        'ParaIdName;DataType;ServerName;Index;Value;Use\n'
        'PrimionIdx;;;-1;0;1\n'
        'DPS_Pdrift_Ctrl_Val;;;-1;2.3;1\n'
        'DPS_Pdrift_Ctrl_OnOff;;;-1;True;1\n'
        'Disabled;;;-1;42;0\n',
        encoding='utf-8',
    )
    (tmp_path / '00_H3O+.csv').write_text(
        'ParaIdName;DataType;ServerName;Index;Value;Use\n'
        'TransmissionIdx;;;-1;6;1\n',
        encoding='utf-8',
    )
    (tmp_path / 'notes.csv').write_text('not a preset', encoding='utf-8')

    presets = parse_presets_directory(tmp_path)

    assert [name for name, _ in presets.values()] == ['H3O+', 'N2x']
    n2x_values = presets[1][1]
    assert {key.name: value for key, value in n2x_values.items()} == {
        'PrimionIdx': 0,
        'DPS_Pdrift_Ctrl_Val': 2.3,
        'DPS_Pdrift_Ctrl_OnOff': True,
    }

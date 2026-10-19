"""Finish margins, with local metadata evidence separate from unverified rules.

The native enum and DIFFTIME_TO_LENGTH are read from the installed metadata.
The category cutoffs and the scaled-time input are an explicit interpretation,
not recovered native method bodies. UI labels must therefore carry an ≈ mark.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import struct


# Native enum names paired with result labels seen in the Global client.
# These are inclusive *model* cutoffs in metres; native rounding is unverified.
CATEGORIES = (
    ('Nose', 'Nose', .2), ('Head', 'Head', .4), ('Neck', 'Neck', .8),
    ('Half', '1/2 L', 1.25), ('ThreeQuarters', '3/4 L', 1.875),
    ('One', '1 L', 2.5), ('OneAndOneQuarters', '1 1/4 L', 3.125),
    ('OneAndHalf', '1 1/2 L', 3.75), ('OneAndThreeQuarters', '1 3/4 L', 4.375),
    ('Two', '2 L', 5.), ('TwoAndHalf', '2 1/2 L', 6.25),
    ('Three', '3 L', 7.5), ('ThreeAndHalf', '3 1/2 L', 8.75),
    ('Four', '4 L', 10.), ('Five', '5 L', 12.5), ('Six', '6 L', 15.),
    ('Seven', '7 L', 17.5), ('Eight', '8 L', 20.), ('Nine', '9 L', 22.5),
    ('Ten', '10 L', 25.), ('OverTen', 'Distance', math.inf),
)


def read_finish_rules(path: Path) -> dict:
    """Read only the two relevant v31 types, never execute the game DLL."""
    raw = path.read_bytes()
    if struct.unpack_from('<II', raw) != (0xFAB11BAF, 31):
        raise ValueError('Unsupported finish-rule metadata version')

    def table(index, size):
        start, length = struct.unpack_from('<II', raw, 8 + index * 8)
        if start + length > len(raw) or length % size:
            raise ValueError('Invalid metadata table')
        return start, length // size

    strings, nstrings = table(2, 1)
    types, ntypes = table(19, 88)
    fields, nfields = table(11, 12)
    defaults, ndefaults = table(7, 12)
    values, nvalues = table(8, 1)
    default_offsets = {struct.unpack_from('<iii', raw, defaults + i * 12)[0]:
                       struct.unpack_from('<iii', raw, defaults + i * 12)[2] for i in range(ndefaults)}

    def name(index):
        if not 0 <= index < nstrings:
            raise ValueError('Invalid metadata string')
        start = strings + index
        return raw[start:raw.index(0, start, strings + nstrings)].decode('utf-8')

    def enum_number(at):
        first = raw[at]
        if first < 0x80:
            unsigned = first
        elif first < 0xc0:
            unsigned = ((first & 0x3f) << 8) | raw[at + 1]
        elif first < 0xe0:
            unsigned = ((first & 0x1f) << 24) | (raw[at+1] << 16) | (raw[at+2] << 8) | raw[at+3]
        elif first == 0xf0:
            unsigned = struct.unpack_from('<I', raw, at + 1)[0]
        elif first == 0xff:
            return -1
        else:
            raise ValueError('Invalid compressed enum value')
        return -(unsigned >> 1) - 1 if unsigned & 1 else unsigned >> 1

    constants, enum = {}, {}
    wanted = {'DIFFTIME_TO_LENGTH', 'BASHIN_INT2FLOAT_ACCURACY', 'FINISHTIME_ACCURACY'}
    for i in range(ntypes):
        at = types + i * 88
        type_name = name(struct.unpack_from('<I', raw, at)[0])
        if type_name not in ('RaceUtil', 'HorseLength'):
            continue
        start = struct.unpack_from('<i', raw, at + 32)[0]
        count = struct.unpack_from('<H', raw, at + 68)[0]
        if not 0 <= start <= nfields - count:
            raise ValueError('Invalid metadata field range')
        for j in range(count):
            index = start + j
            key = name(struct.unpack_from('<I', raw, fields + index * 12)[0])
            offset = default_offsets.get(index, -1)
            if offset < 0:
                continue
            if not 0 <= offset < nvalues:
                raise ValueError('Invalid metadata default')
            if type_name == 'HorseLength' and key != 'value__':
                enum[key] = enum_number(values + offset)
            elif type_name == 'RaceUtil' and key in wanted:
                constants[key] = enum_number(values + offset) if key == 'FINISHTIME_ACCURACY' else struct.unpack_from('<f', raw, values + offset)[0]
    if set(constants) != wanted or set(enum) != {c[0] for c in CATEGORIES}:
        raise ValueError('Incomplete native finish constants / HorseLength enum')
    if any(not math.isfinite(v) or v <= 0 for v in constants.values()):
        raise ValueError('Invalid native finish constants')
    return {'metadata_sha256': hashlib.sha256(raw).hexdigest(), 'constants': constants,
            'horse_length_enum': enum, 'native_bodies_recovered': False}


def build_finish_margins(scaled_times: list[float], native: dict | None) -> tuple[list[dict | None], dict]:
    if not scaled_times or any(not math.isfinite(t) or t <= 0 for t in scaled_times):
        raise ValueError('Finish times must be finite and positive')
    rules = {'version': 'finish-margins-1', 'native': native,
             'time_input': 'scaled finish time before scoreboard correction; full precision',
             'category_status': 'approximate: native thresholds, rounding and time-input call chain unverified',
             'cutoffs_metres': {key: metres for key, _, metres in CATEGORIES if math.isfinite(metres)},
             'metres_per_length': 2.5, 'reference': 'previous finisher, not winner'}
    result = [None] * len(scaled_times)
    if native is None:
        rules['unavailable'] = 'Local finish-rule metadata unavailable'
        return result, rules
    order = sorted(range(len(scaled_times)), key=lambda i: (scaled_times[i], i))
    for ahead, index in zip(order, order[1:]):
        delta = scaled_times[index] - scaled_times[ahead]
        metres = delta * native['constants']['DIFFTIME_TO_LENGTH']
        name, label, _ = next(c for c in CATEGORIES if metres <= c[2])
        result[index] = {'previous_runner': ahead, 'seconds': delta, 'metres': metres,
                         'lengths': metres / 2.5, 'label': label, 'approximate': True,
                         'native_enum_name': name, 'native_enum_value': native['horse_length_enum'][name]}
    return result, rules


def format_board_time(seconds: float) -> str:
    # Truncate to tenths, matching the client-style m:ss.d presentation.
    # Native rounding implementation still requires verification.
    tenths = math.floor(seconds * 10)
    minutes, rest = divmod(tenths, 600)
    return f'{minutes}:{rest // 10:02d}.{rest % 10}'

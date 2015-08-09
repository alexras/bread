from bitstring import BitArray
from .field import BreadField


def encode_bool(value):
    return BitArray(bool=value)


def decode_bool(encoded):
    return encoded.bool


def boolean(parent, **field_options):
    return BreadField(
        1, encode_bool, decode_bool,
        str_format=field_options.get('str_format', None))

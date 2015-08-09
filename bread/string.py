from bitstring import BitArray
from .field import BreadField


def string(length):
    def make_string_field(parent, **field_options):
        length_in_bits = length * 8

        def encode_string(value):
            if type(value) != bytes:
                value = value.encode('utf-8')

            return BitArray(bytes=value)

        def decode_string(encoded):
            return encoded.bytes

        return BreadField(length_in_bits, encode_string, decode_string,
                          str_format=field_options.get('str_format', None))

    return make_string_field

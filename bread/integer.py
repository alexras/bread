from bitstring import BitArray

from .constants import BIG_ENDIAN
from .field import BreadField


def intX(length, signed=False):
    def make_intX_field(parent, **field_options):
        if length % 8 == 0 and length >= 8:
            int_type_key = None

            if signed:
                int_type_key = 'int'
            else:
                int_type_key = 'uint'

            if field_options.get('endianness', None) == BIG_ENDIAN:
                int_type_key += 'be'
            else:
                int_type_key += 'le'

            offset = field_options.get('offset', 0)

            def encode_intX(value):
                options = {}
                options[int_type_key] = value - offset
                options['length'] = length

                return BitArray(**options)

            def decode_intX(encoded):
                return getattr(encoded, int_type_key) + offset
        else:
            offset = field_options.get('offset', 0)

            def encode_intX(value):
                value -= offset

                if signed:
                    return BitArray(int=value, length=length)
                else:
                    return BitArray(uint=value, length=length)

            def decode_intX(encoded):
                if signed:
                    decoded = encoded.int
                else:
                    decoded = encoded.uint

                return decoded + offset

        return BreadField(
            length, encode_intX, decode_intX,
            str_format=field_options.get('str_format', None))

    return make_intX_field


uint8 = intX(length=8, signed=False)
byte = uint8
uint16 = intX(length=16, signed=False)
uint32 = intX(length=32, signed=False)
uint64 = intX(length=64, signed=False)
int8 = intX(length=8, signed=True)
int16 = intX(length=16, signed=True)
int32 = intX(length=32, signed=True)
int64 = intX(length=64, signed=True)
bit = intX(1, signed=False)
semi_nibble = intX(2, signed=False)
nibble = intX(4, signed=False)

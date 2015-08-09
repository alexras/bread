from bitstring import pack
from .field import BreadField


def padding(length):   # pragma: no cover
    def make_padding_field(parent, **field_options):
        def encode_pad(value):
            return pack('pad:n', n=value)

        def decode_pad(encoded):
            return None

        return BreadField(
            length, encode_pad, decode_pad,
            str_format=field_options.get('str_format', None))

    return make_padding_field

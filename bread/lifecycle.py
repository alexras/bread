import math

from bitstring import BitArray

from .struct import BreadStruct, build_struct

from .vendor import six


def new(spec, type_name='bread_struct', data=None):
    struct = build_struct(spec, type_name)

    if data is None:
        data = BitArray(bytearray(int(math.ceil(len(struct) / 8.0))))

    if len(struct) > len(data):
        raise ValueError(
            ("Data being parsed isn't long enough; expected at least %d "
             "bits, but data is only %d bits long") %
            (len(struct), len(data)))

    struct._set_data(data[:len(struct)])
    struct._offset = 0

    return struct


def parse(data_source, spec, type_name='bread_struct'):
    if type(data_source) == str:
        data_bits = BitArray(bytes=six.b(data_source))
    elif type(data_source) == list:
        data_bits = BitArray(bytes=data_source)
    else:
        data_bits = BitArray(data_source)

    return new(spec, type_name=type_name, data=data_bits)


def write(parsed_obj, spec=None, filename=None):
    """Writes an object created by `parse` to either a file or a bytearray.

    If the object doesn't end on a byte boundary, zeroes are appended to it
    until it does.
    """
    if not isinstance(parsed_obj, BreadStruct):
        raise ValueError(
            'Object to write must be a structure created '
            'by bread.parse')

    if filename is not None:
        with open(filename, 'wb') as fp:
            parsed_obj._data_bits.tofile(fp)
    else:
        return bytearray(parsed_obj._data_bits.tobytes())

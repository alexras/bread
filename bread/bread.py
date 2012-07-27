# Heavily inspired by (and some parts blatantly yanked from) y4k's newstruct.py
# (https://raw.github.com/theY4Kman/pysmx/master/smx/newstruct.py)

import struct, copy

little_endian = 0
big_endian = 1

def mask_bits(byte, start_bit, stop_bit):
    return (((byte << start_bit) & 0xff)
            >> (7 - stop_bit + start_bit)) & 0xff

def substring_bits(data, start_bit, end_bit):
    start_byte = start_bit / 8
    end_byte = end_bit / 8

    shift_amount = start_bit % 8

    byte_list = []

    for current_index in xrange(start_byte, end_byte):
        current_byte = data[current_index]
        next_byte = data[current_index + 1]

        first_byte_chunk = mask_bits(current_byte, shift_amount, 7)
        second_byte_chunk = mask_bits(next_byte, 0, shift_amount - 1)

        shifted_byte = (first_byte_chunk << shift_amount) | second_byte_chunk

        byte_list.append(shifted_byte)

    if (start_byte == end_byte) or (end_bit - start_bit + 1 > 8):
        byte_list.append(mask_bits(data[end_byte], shift_amount, end_bit % 8))

    return byte_list

class Field(object):
    """
    The base class from which all fields derive.
    """

    creation_counter = 0

    def __init__(self, length):
        self.creation_counter = Field.creation_counter
        self.length = length

        Field.creation_counter += 1

    def load(self, data, **kwargs):
        raise NotImplementedError("All fields must implement load()")

    def __len__(self):
        return self.length

class Struct(object):
    endianness = little_endian

    def __new__(cls, *args, **kwargs):
        if len(filter(lambda x: x.find('_bread_field_') != -1, dir(cls))) == 0:
            # Fields haven't been initialized yet, since this is the first time
            # we're creating a new instance of this object

            fields = map(lambda y: (y, getattr(cls, y)),
                         filter(lambda x: x[0] != '_' and
                                (issubclass(type(getattr(cls, x)), Struct) or
                                 issubclass(type(getattr(cls, x)), Field)),
                                dir(cls)))
            fields.sort(key = lambda x: x[1].creation_counter)

            cls._bread_field_order = map(lambda x: x[0], fields)

            for (field_name, field) in fields:
                delattr(cls, field_name)
                setattr(cls, "_bread_field_" + field_name, field)

            if hasattr(cls, "endianness"):
                endianness = getattr(cls, "endianness")
                delattr(cls, "endianness")
                setattr(cls, "_bread_endianness", endianness)

        obj = super(Struct, cls).__new__(cls, *args, **kwargs)

        obj._bread_endianness = cls._bread_endianness

        for field in cls._bread_field_order:
            hidden_field_name = "_bread_field_" + field

            setattr(obj, hidden_field_name,
                    copy.deepcopy(getattr(obj, hidden_field_name)))

        return obj

    def load(self, data_source):
        bits_loaded = 0

        if type(data_source) == file:
            data = map(ord, data_source.read())
        elif type(data_source) == str:
            data = map(ord, data_source)
        elif type(data_source) == bytearray:
            data = data_source
        else:
            raise ValueError("Can't parse data source of type '%s'",
                             type(data_source))

        for field_name in self._bread_field_order:
            field = getattr(self, "_bread_field_" + field_name)

            field_length_bits = len(field)

            field_bytes = substring_bits(
                data, bits_loaded, bits_loaded + field_length_bits - 1)

            try:
                field_val = field.load(
                    field_bytes, endianness = self._bread_endianness)
                bits_loaded += field_length_bits
            except Exception, e:
                if not e.args:
                    e.args = ['']

                e.args = (("Parsing field '%s' failed: " % (field_name))
                          + e.args[0],) + e.args[1:]

                raise e

            setattr(self, field_name, field_val)

# Mapping from (length, signed) pairs to struct symbols
STRUCT_CONVERSION_SYMBOLS = {
    (8, True) : 'b',
    (8, False) : 'B',
    (16, True) : 'h',
    (16, False) : 'H',
    (32, True) : 'i',
    (32, False) : 'I',
    (64, True) : 'q',
    (64, False) : 'Q'
    }

class Integer(Field):
    def load(self, data, **kwargs):
        conversion = ''

        if "endianness" in kwargs:
            if kwargs["endianness"] == little_endian:
                conversion = '<'
            elif kwargs["endianness"] == big_endian:
                conversion = ">"

        conversion += self.struct_conversion
        return struct.unpack(conversion, ''.join(map(chr, data)))[0]

    def __init__(self, length, signed):
        self.struct_conversion = STRUCT_CONVERSION_SYMBOLS[(length, signed)]
        self.length = length

        super(Integer, self).__init__(length)

class Int8(Integer):
    def __init__(self):
        super(Int8, self).__init__(8, True)

class UInt8(Integer):
    def __init__(self):
        super(UInt8, self).__init__(8, False)

class Int16(Integer):
    def __init__(self):
        super(Int16, self).__init__(16, True)

class UInt16(Integer):
    def __init__(self):
        super(UInt16, self).__init__(16, False)

class Int32(Integer):
    def __init__(self):
        super(Int32, self).__init__(32, True)

class UInt32(Integer):
    def __init__(self):
        super(UInt32, self).__init__(32, False)

class Int64(Integer):
    def __init__(self):
        super(Int64, self).__init__(64, True)

class UInt64(Integer):
    def __init__(self):
        super(UInt64, self).__init__(64, False)

class String(Field):
    def __init__(self, length):
        super(String, self).__init__(length)

    def load(self, data, **kwargs):
        return struct.unpack("%ds" % self.length, data)

class Bool(Field):
    def __init__(self):
        super(Bool, self).__init__(1)

    def load(self, data, **kwargs):
        data = data[0]

        if data == 1:
            return True
        elif data == 0:
            return False
        else:
            raise ValueError("Invalid boolean value %d" % (data))

class Padding(Field):
    def __init__(self, length):
        super(Padding, self).__init__(length)

    def load(self, data, **kwargs):
        return None

class Enum(Field):
    def __init__(self, length, enum_values):
        self.length = length
        self.enum_values = enum_values

        if type(enum_values.keys()[0]) is tuple:
            self.key_ranges = True
        elif type(enum_values.keys()[0]) is int:
            self.key_ranges = False
        else:
            raise ValueError("Enum keys must be ints or tuples")

        if self.length == 1:
            self.substruct = Bit()
        elif self.length == 2:
            self.substruct = SemiNibble()
        elif self.length == 4:
            self.substruct = Nibble()
        elif self.length == 8:
            self.substruct = UInt8()
        elif self.length == 16:
            self.substruct = UInt16()
        elif self.length == 32:
            self.substruct = UInt32()
        elif self.length == 64:
            self.substruct = UInt64()
        else:
            raise ValueError("bread doesn't currently support enums with keys "
                             "larger than 64 bits")

    def load(self, data, **kwargs):
        enum_key = self.substruct.load(data, **kwargs)

        if self.key_ranges:
            for key_range, val in self.enum_values.items():
                if enum_key in xrange(*key_range):
                    return val
            raise ValueError("%d is not a valid enum value" % (enum_key))
        else:
            if enum_key in enum_values:
                return enum_values[enum_key]
            else:
                raise ValueError("%d is not a valid enum value" % (enum_key))

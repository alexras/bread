# Heavily inspired by (and some parts blatantly yanked from) y4k's newstruct.py
# (https://raw.github.com/theY4Kman/pysmx/master/smx/newstruct.py)

import struct, copy

little_endian = 0
big_endian = 1

class Field(object):
    """
    The base class from which all fields derive.
    """

    creation_counter = 0

    def __init__(self, length, struct_conversion):
        self.data = None
        self.length = length
        self.struct_conversion = struct_conversion

        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

    def load(self, data_source, offset):
        if type(data_source) == file:
            self.data = data_source.read(self.length)
        elif type(data_source) == str:
            self.data = data_source[offset:offset + self.length]

        return self.length

    def unpack(self):
        return struct.unpack(self.struct_conversion, self.data)

class FieldDescriptor(object):
    def __init__(self, field_name):
        self.field_name = "_bread_field_" + field_name

    def __get__(self, instance, owner):
        return getattr(instance, self.field_name).unpack()

    def __set__(self, value):
        raise AttributeError

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

    def __getattr__(self, name):
        if name not in self._bread_field_order:
            raise AttributeError

        return object.__getattribute__(self, "_bread_field_" + name).unpack(
            endianness = self._bread_endianness)

    def load(self, data_source):
        amt_loaded = 0
        for field in self._bread_field_order:
            amt_loaded += getattr(self, "_bread_field_" + field).load(
                data_source, amt_loaded)

# Mapping from (length, signed) pairs to struct symbols
STRUCT_CONVERSION_SYMBOLS = {
    (1, True) : 'b',
    (1, False) : 'B',
    (2, True) : 'h',
    (2, False) : 'H',
    (4, True) : 'i',
    (4, False) : 'I',
    (8, True) : 'q',
    (8, False) : 'Q'
    }

class Integer(Field):
    def unpack(self, **kwargs):
        conversion = ''

        if "endianness" in kwargs:
            if kwargs["endianness"] == little_endian:
                conversion = '<'
            elif kwargs["endianness"] == big_endian:
                conversion = ">"

        old_conversion = self.struct_conversion
        self.struct_conversion = conversion + self.struct_conversion

        int_to_return = super(Integer, self).unpack()[0]

        self.struct_conversion = old_conversion

        return int_to_return

    def __init__(self, length, signed):
        self.struct_conversion = STRUCT_CONVERSION_SYMBOLS[(length, signed)]

        super(Integer, self).__init__(length, self.struct_conversion)

class Int8(Integer):
    def __init__(self):
        super(Int8, self).__init__(1, True)

class UInt8(Integer):
    def __init__(self):
        super(UInt8, self).__init__(1, False)

class Int16(Integer):
    def __init__(self):
        super(Int16, self).__init__(2, True)

class UInt16(Integer):
    def __init__(self):
        super(UInt16, self).__init__(2, False)

class Int32(Integer):
    def __init__(self):
        super(Int32, self).__init__(4, True)

class UInt32(Integer):
    def __init__(self):
        super(UInt32, self).__init__(4, False)

class Int64(Integer):
    def __init__(self):
        super(Int64, self).__init__(8, True)

class UInt64(Integer):
    def __init__(self):
        super(UInt64, self).__init__(8, False)


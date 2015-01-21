import types, collections, functools, json
from bitstring import BitArray, pack

from .vendor.six.moves import range

LITTLE_ENDIAN = 0
BIG_ENDIAN = 1
CONDITIONAL = 2

# Enumeration of different operations that field descriptors can perform
READ = 0
WRITE = 1

class BreadField(object):
    def __init__(self, length, encode_fn, decode_fn, str_format):
        self._data_bits = None
        self._offset = None
        self._length = length
        self._cached_value = None

        self._encode_fn = encode_fn
        self._decode_fn = decode_fn

        self._str_format = str_format

        self.name = None

    @property
    def length(self):
        return self._length

    def _set_data(self, data_bits):
        self._data_bits = data_bits

    def get(self):
        if self._cached_value is None:
            start_bit = self._offset
            end_bit = self._offset + self.length

            value_bits = self._data_bits[start_bit:end_bit]
            self._cached_value = self._decode_fn(value_bits)

        return self._cached_value

    def as_json(self):
        return self.get()

    def set(self, value):
        value_bits = self._encode_fn(value)

        self._data_bits.overwrite(value_bits.bin, self._offset)

        self._cached_value = value

    def copy(self):
        return BreadField(self._length, self._encode_fn, self._decode_fn,
                          self._str_format)

BREAD_CONDITIONAL_RESERVED_FIELDS = (
    '_parent_struct', '_conditional_field_name', '_conditions')

class BreadConditional(object):
    def __init__(self, conditional_field_name, parent_struct):
        self._parent_struct = parent_struct
        self._conditional_field_name = conditional_field_name
        self._conditions = {}


    def _set_data(self, data_bits):
        for struct in self._conditions.values():
            struct._set_data(data_bits)

    def _add_condition(self, predicate_value, struct):
        self.conditions[predicate_value] = struct

    def _get_condition(self):
        switch_value = self._parent_struct.get(self._conditional_field_name)

        if switch_value not in self._conditions:
            raise AttributeError("No known conditional case '%s'" %
                                 (str(switch_value)))

        return switch_value

    def __getattr__(self, attr):
        if attr in BREAD_CONDITIONAL_RESERVED_FIELDS:
            return super(BreadConditional, self).__getattr__(attr)
        else:
            return self._conditions[self._get_condition()].__getattr__(attr)

    def __setattr__(self, attr, value):
        if attr in BREAD_CONDITIONAL_RESERVED_FIELDS:
            return super(BreadConditional, self).__setattr__(attr, value)
        else:
            self._conditions[self._get_condition()].__setattr__(attr, value)

    def as_json(self):
        return self._conditions[self._get_condition()].as_json()

    @property
    def _offset(self):
        return self._conditions[self._conditions.keys()[0]]._offset

    @_offset.setter
    def _offset(self, off):
        for condition_struct in self._conditions:
            condition_struct._offset = off

    def copy(self):
        copy = BreadConditional(
            self._conditional_field_name, self._parent_struct)

        for condition, struct in self._conditions:
            copy._add_condition(condition, struct.copy())

        return copy

class BreadArray(object):
    def __init__(self, num_items, item_template):
        self._items = []
        self._num_items = num_items
        self.name = None

        if item_template is not None:
            for i in range(num_items):
                self._items.append(item_template.copy())

    @property
    def length(self):
        return sum(map(lambda x: x.length, self._items))

    def __getitem__(self, index):
        return self._items[index].get()

    def __setitem__(self, index, value):
        self._items[index].set(value)

    def get(self):
        return map(lambda x: x.get(), self._items)

    def set(self, value):
        if type(value) != list:
            raise ValueError('Cannot set an array using a %s value' %
                             (str(type(value))))
        if len(value) != self._num_items:
            raise ValueError(
                'Cannot change the length of an array '
                '(would have changed from %d to %d)'
                % (self._num_items, len(value)))

        for i, item in enumerate(value):
            self._items[i].set(item)

    def copy(self):
        array_copy = BreadArray(self._num_items, self._items[0])
        return array_copy

    def as_json(self):
        return map(lambda item: item.as_json(), self._items)

    def _set_data(self, data_bits):
        for item in self._items:
            item._set_data(data_bits)

    @property
    def _offset(self):
        return self._items[0]._offset

    @_offset.setter
    def _offset(self, value):
        offset = value

        for item in self._items:
            item._offset = offset
            offset += item.length

BREAD_STRUCT_RESERVED_FIELDS = (
    '_fields', '_field_list', '_data_bits', '_add_field', '__offsets__',
    '_conditional_fields', '_LENGTH', '_offset', 'name')

class BreadStruct(object):
    def __init__(self):
        self._data_bits = None
        self._fields = {}
        self._conditional_fields = []
        self._field_list = []
        self.name = None

        # __offsets__ retained for backwards compatibility
        class Offsets(object):
            pass
        self.__offsets__ = Offsets()

    def __eq__(self, other):
        if not hasattr(other, '_data_bits'):
            return False

        return self._data_bits == other._data_bits

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self):
        return self._LENGTH

    @property
    def length(self):
        return self._LENGTH

    def __str__(self):
        string = '\n'

        for field in self._field_list:
            string += str(field) + '\n'

    def __repr__(self):
        return self.__str__(self)

    def _set_data(self, data_bits):
        self._data_bits = data_bits

        for field in self._field_list:
            field._set_data(data_bits)

    @property
    def _offset(self):
        # A struct's offset is the offset where its first field starts
        return self._field_list[0]._offset

    @_offset.setter
    def _offset(self, value):
        offset = value

        # All fields offsets are relative to the starting offset for the struct
        for field in self._field_list:
            field._offset = offset
            offset += field.length

        for name, field in self._fields.items():
            setattr(self.__offsets__, name, field._offset)

    # _LENGTH retained for backwards compatibility
    @property
    def _LENGTH(self):
        return sum(map(lambda x: x.length, self._field_list))

    def __getattr__(self, attr):
        if attr in BREAD_STRUCT_RESERVED_FIELDS:
            return super(BreadStruct, self).__getattr__(attr)

        if attr in self._fields:
            return self._fields[attr].get()

        for conditional_field in self._conditional_fields:
            try:
                return getattr(conditional_field, attr)
            except AttributeError:
                pass

        raise AttributeError("No known field '%s'" % (attr))

    def __setattr__(self, attr, value):
        if attr in BREAD_STRUCT_RESERVED_FIELDS:
            return super(BreadStruct, self).__setattr__(attr, value)

        if attr not in self._fields:
            raise AttributeError("No known field '%s'" % (attr))

        field = self._fields[attr]
        field.set(value)

    def _add_field(self, field, name=None):
        if name is not None:
            self._fields[name] = field
            field.name = name

        self._field_list.append(field)

    def copy(self):
        copy = BreadStruct()

        for name, field in self._fields.items():
            copy._add_field(field.copy(), name)

        return copy

    def as_json(self):
        json_struct = {}

        for field in self._field_list:
            if field.name is not None:
                json_struct[field.name] = field.as_json()

        return json.dumps(json_struct)

    def as_native(self):
        # FIXME FINISH
        pass


# BEGIN TYPE INFORMATION

def intX(length, signed=False):
    def make_intX_field(**field_options):
        int_type_key = None

        if signed:
            int_type_key = 'int'
        else:
            int_type_key = 'uint'

        if field_options.get('endianness', None) == LITTLE_ENDIAN:
            int_type_key += 'le'
        else:
            int_type_key += 'be'

        offset = field_options.get('offset', 0)

        def encode_intX(value):
            options = {}
            options[int_type_key] = value
            options['length'] = length

            return BitArray(**options)

        def decode_intX(encoded):
            return getattr(encoded, int_type_key) + offset

        return BreadField(
            length, encode_intX, decode_intX,
            str_format=field_options.get('str_format', None))

    return make_intX_field

uint8  = intX(length=8,  signed=False)
byte = uint8
uint16 = intX(length=16, signed=False)
uint32 = intX(length=32, signed=False)
uint64 = intX(length=64, signed=False)
int8   = intX(length=8,  signed=True)
int16  = intX(length=16, signed=True)
int32  = intX(length=32, signed=True)
int64  = intX(length=64, signed=True)
bit = intX(1, signed=False)
semi_nibble = intX(2, signed=False)
nibble = intX(4, signed=False)

def string(length):
    def make_string_field(**field_options):
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

def encode_bool(value):
    return BitArray(bool=value)

def decode_bool(encoded):
    return encoded.bool

def boolean(**field_options):
    return BreadField(
        1, encode_bool, decode_bool,
        str_format=field_options.get('str_format', None))

def padding(length):
    def make_padding_field(**field_options):
        def encode_pad(value):
            return pack('pad:n', n=value)

        def decode_pad(encoded):
            return None

        return BreadField(
            length, encode_pad, decode_pad,
            str_format=field_options.get('str_format', None))

    return make_padding_field

def enum(length, values, default=None):
    def make_enum_field(**field_options):
        enum_field = intX(length, signed=False)(**field_options)

        old_encode_fn = enum_field._encode_fn
        old_decode_fn = enum_field._decode_fn

        def encode_enum(value):
            return old_encode_fn(values[value])

        def decode_enum(encoded):
            return values[old_decode_fn(encoded)]

        enum_field._encode_fn = encode_enum
        enum_field._decode_fn = decode_enum

        return enum_field

    return make_enum_field

def array(length, substruct):
    def make_array_field(**field_options):
        if type(substruct) == list:
            built_substruct = build_struct(spec=substruct)
        else:
            built_substruct = substruct()

        return BreadArray(length, built_substruct)

    return make_array_field

# END TYPE INFORMATION

def build_struct(spec, type_name=None):
    # Give different structs the appearance of having different type names
    class NewStruct(BreadStruct):
        pass

    if type_name is not None:
        NewStruct.__name__ = type_name

    struct = NewStruct()

    global_options = {}

    spec = collections.deque(spec)

    # Read specification one line at a time, greedily consuming bits from the
    # stream as you go
    while len(spec) > 0:
        spec_line = spec.popleft()

        if type(spec_line) == dict:
            # A dictionary in the spec indicates global options for parsing
            global_options = spec_line
        elif isinstance(spec_line, types.FunctionType) or len(spec_line) == 1:
            # This part of the spec doesn't have a name; evaluate the function
            # to get the field object and then give that object a fake name.
            # Spec lines of length 1 are assumed to be functions.

            if isinstance(spec_line, types.FunctionType):
                field = spec_line
            else:
                field = spec_line[0]

            # Don't give the field a name
            struct._add_field(field(**global_options))

        elif spec_line[0] == CONDITIONAL:
            predicate_field_name, conditions = spec_line[1:]

            field = BreadConditional(predicate_field_name, struct)

            for predicate_value, condition in conditions.items():
                condition_struct = build_struct(condition)
                field._add_condition(predicate_value, condition_struct)

            struct._add_field(field)
        else:
            field_name = spec_line[0]
            field = spec_line[1]
            options = global_options

            # Options for this field, if any, override the global options
            if len(spec_line) == 3:
                options = global_options.copy()
                options.update(spec_line[2])

            if type(field) == list:
                struct._add_field(build_struct(field), field_name)
            else:
                struct._add_field(field(**options), field_name)

    return struct


def parse(data_source, spec, type_name='bread_struct'):
    if type(data_source) == str:
        data_bits = BitArray(bytes=data_source)
    elif type(data_source) == list:
        data_bits = BitArray(bytes=data_source)
    else:
        data_bits = BitArray(data_source)

    struct = build_struct(spec, type_name)

    struct._set_data(data_bits)
    struct._offset = 0

    return struct

def write(parsed_obj, spec, filename=None):
    if filename is not None:
        with open(filename, 'wb') as fp:
            parsed_obj._data_bits.tofile(fp)
    else:
        return parsed_obj._data_bits.tobytes()

# def as_json(self):
#     out_json = self.__json_repr()

#     return json.dumps(out_json)

# def as_native(self):
#     return self.__json_repr()

# def __element_json_repr(self, element):
#     if hasattr(element, "__baked_by_bread__"):
#         return element.__json_repr()
#     else:
#         return element

# def __json_repr(self):
#     out_json = {}

#     for key, formatter in keys:
#         val = getattr(self, key)

#         if isinstance(val, list):
#             out_json[key] = list(map(self.__element_json_repr, val))
#         else:
#             out_json[key] = self.__element_json_repr(val)

#     return out_json

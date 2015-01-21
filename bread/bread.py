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
    def __init__(self, length, encode_fn, decode_fn):
        self._data_bits = None
        self._offset = None
        self._length = length
        self._cached_value = None

        self._encode_fn = encode_fn
        self._decode_fn = decode_fn

    @property
    def length(self):
        return self._length

    def _set_data(self, data_bits):
        self._data_bits = data_bits

    def get(self):
        if self._cached_value is not None:
            start_bit = self._offset
            end_bit = self._offset + self.length

            value_bits = self._data_bits[start_bit:end_bit]
            self._cached_value = self._decode_fn(value_bits)

        return self._cached_value

    def set(self, value):
        value_bits = self._encode_fn(value)

        self._data_bits.overwrite(value_bits.bin, self._offset)

        self._cached_value = value

    def copy(self):
        return BreadField(self._length, self._encode_fn, self._decode_fn)


class BreadArray(object):
    def __init__(self, length, item_template):
        self._items = []

        if item_template is not None:
            for i in range(length):
                self._items.append(item_template._copy())

    def __getitem__(self, index):
        return self._items[index].get()

    def __setitem__(self, index, value):
        self._items[index].set(value)

    def get(self):
        raise KeyError('Cannot retrieve an array directly')

    def set(self, value):
        raise KeyError('Cannot modify an array directly')

    def copy(self):
        copy = BreadArray(length, None)

        for item in self._items:
            copy._items.append(item.copy())

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
            item._offset = value
            offset += item.length


BREAD_STRUCT_RESERVED_FIELDS = (
    '_fields', '_data_bits', '_add_field', '__offsets__', '_LENGTH', 'offset')

class BreadStruct(object):
    def __init__(self):
        self._data_bits = None
        self._fields = {}
        self._field_list = []

        # __offsets__ retained for backwards compatibility
        self.__offsets__ = object()

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
    def _LENGTH():
        return sum(lambda x: x.length, self._field_list)

    def __getattr__(self, attr):
        if attr in BREAD_STRUCT_RESERVED_FIELDS:
            return getattr(super(BreadStruct, self), attr)

        if attr not in self._fields:
            raise AttributeError("No known field '%s'" % (attr))

        field = self._fields[attr]

        return field.get()


    def __setattr__(self, attr, value):
        if attr in BREAD_STRUCT_RESERVED_FIELDS:
            return setattr(super(BreadStruct, self), attr, value)

        if attr not in self._fields:
            raise AttributeError("No known field '%s'" % (attr))

        field = self._fields[attr]
        field.set(value)

    def _add_field(self, name, field):
        self._fields[name] = field
        self._field_list.append(field)

    def _copy(self):
        copy = BreadStruct(self._data_bits)

        for field in self._fields:
            copy._add_field(field.copy())

        return copy

    def as_json(self):
        # FIXME FINISH
        pass

    def as_native(self):
        # FIXME FINISH
        pass


# BEGIN TYPE INFORMATION

def intX(length, signed=False):
    options = {}

    int_type_key = None

    if signed:
        int_type_key = 'int'
    else:
        int_type_key = 'uint'

    if endianness == LITTLE_ENDIAN:
        int_type_key += 'le'
    else:
        int_type_key += 'be'

    options[int_type_key] = value
    options['length'] = length

    def encode_intX(value):
        return BitArray(**options)

    def decode_intX(encoded):
        return getattr(encoded, int_type_key)

    return BreadField(length, encode_intX, decode_intX)

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
    length_in_bits = length * 8

    def encode_string(value):
        if type(value) != bytes:
            value = value.encode('utf-8')

        return BitArray(bytes=value)

    def decode_string(encoded):
        return encoded.bin

    return BreadField(length_in_bits, encode_string, decode_string)

def encode_bool(value):
    return BitArray(bool=value)

def decode_bool(encoded):
    return encoded.bool

def boolean():
    return BreadField(1, encode_bool, decode_bool)

def padding(length):
    def encode_pad(value):
        return pack('pad:n', n=value)

    def decode_pad(encoded):
        return None

    return BreadField(length, encode_pad, decode_pad)

def enum(length, values, default=None):
    enum_field = int_X(length, signed=False)

    old_encode_fn = enum_field.encode_fn
    old_decode_fn = enum_field.decode_fn

    def encode_enum(value):
        return old_encode_fn(values[value])

    def decode_enum(encoded):
        return values[old_decode_fn(encoded)]

    enum_field._encode_fn = encode_enum
    enum_field._decode_fn = decode_enum

    return enum_field

def array(length, substruct):
    if type(substruct) == list:
        substruct = build_struct(spec=substruct)

    return BreadArray(length, substruct)

# END TYPE INFORMATION

def build_struct(spec, type_name):
    # Give different structs the appearance of having different type names
    class NewStruct(BreadStruct):
        pass

    NewStruct.__name__ = type_name

    struct = NewStruct()

    global_options = {}

    spec = collections.deque(spec)

    unnamed_fields = 1

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

            field.set_options(**global_options)
            struct._add_field('_unnamed_%d' % (unnamed_fields), field)
            unnamed_fields += 1
        elif spec_line[0] == CONDITIONAL:
            # FIXME FINISH
        else:
            field_name = spec_line[0]
            field = spec_line[1]
            options = global_options

            # Options for this field, if any, override the global options
            if len(spec_line) == 3:
                options = global_options.copy()
                options.update(spec_line[2])

            field.set_options(**options)

            struct._add_field(field_name, field)

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

def process_spec(spec, handle_function, handle_field, handle_conditional):
    global_options = {}

    spec = collections.deque(spec)

    # Read specification one line at a time, greedily consuming bits from the
    # stream as you go
    while len(spec) > 0:
        spec_line = spec.popleft()

        if type(spec_line) == dict:
            # A dictionary in the spec indicates global options for parsing
            global_options = spec_line
        elif isinstance(spec_line, types.FunctionType):
            # If the spec contains a function, that function should be applied
            # to the input stream (this is typically done to parse padding bits)
            try:
                handle_function(spec_line, global_options)
            except Exception as e:
                print("Error while processing %s: %s" % (spec_line, e))
                raise e
        elif len(spec_line) == 1:
            # Spec lines of length 1 are assumed to be functions, which are
            # treated the same as before
            try:
                handle_function(spec_line[0], global_options)
            except Exception as e:
                print("Error while processing %s: %s" % (spec_line, e))
                raise e
        elif spec_line[0] == CONDITIONAL:
            # Push appropriate conditional spec on the front of the current
            # one so that it will be evaluated next

            handle_conditional(spec_line[1], spec_line[2], spec)
        else:
            field_name = spec_line[0]
            parse_function = spec_line[1]
            options = global_options

            # Options for this field, if any, override the global options
            if len(spec_line) == 3:
                options = global_options.copy()
                options.update(spec_line[2])

            try:
                handle_field(field_name, parse_function, options)
            except Exception as e:
                print("Error while processing field '%s': %s" % (
                    field_name, e))
                raise e

def parse_from_reader(reader, spec, type_name='bread_struct', **kwargs):
    offsets = {}
    keys = []
    length = 0
    parsed_dict = {}

    start_reader_offset = reader.pos

    def handle_function(parse_function, options):
        parse_function(READ, reader, None, **options)

    def handle_field(field_name, parse_function, options):
        if "str_format" in options:
            formatter = options["str_format"]
        else:
            formatter = str

        keys.append((field_name, formatter))

        offsets[field_name] = reader.pos

        if type(parse_function) == list:
            val = parse_from_reader(reader, parse_function, **options)
        else:
            val = parse_function(READ, reader, None, **options)

        if val is not None:
            parsed_dict[field_name] = val

    def handle_conditional(
            conditional_field_name, conditional_clauses, spec_deque):
        conditional_val = parsed_dict[conditional_field_name]
        condition_spec = conditional_clauses[conditional_val]

        for spec_item in reversed(condition_spec):
            spec_deque.appendleft(spec_item)

    process_spec(spec, handle_function, handle_field, handle_conditional)

    class bread_struct_offsets(object):
        def __eq__(self, other):
            return self.__dict__ == other.__dict__

        def __ne__(self, other):
            return not self.__eq__(other)

    offsets_obj = bread_struct_offsets()

    for key, value in list(offsets.items()):
        setattr(offsets_obj, key, value)

    parsed_dict["__offsets__"] = offsets_obj
    parsed_dict["_LENGTH"] = reader.pos - start_reader_offset

    class NewStruct(object):
        def __eq__(self, other):
            for key in list(self.__dict__.keys()):
                if key not in other.__dict__:
                    return False
                elif self.__dict__[key] != other.__dict__[key]:
                    return False
            return True


        def __ne__(self, other):
            return not self.__eq__(other)

        def __len__(self):
            return self._LENGTH

        def __str__(self):
            string = "\n"

            for key, formatter in keys:
                string += "%s: %s\n" % (key, formatter(getattr(self, key)))

            return string

        def __repr__(self):
            return self.__str__()

        def __getattr__(self, name):
            raise AttributeError("No known field '%s'" % (name))

        def as_json(self):
            out_json = self.__json_repr()

            return json.dumps(out_json)

        def as_native(self):
            return self.__json_repr()

        def __element_json_repr(self, element):
            if hasattr(element, "__baked_by_bread__"):
                return element.__json_repr()
            else:
                return element

        def __json_repr(self):
            out_json = {}

            for key, formatter in keys:
                val = getattr(self, key)

                if isinstance(val, list):
                    out_json[key] = list(map(self.__element_json_repr, val))
                else:
                    out_json[key] = self.__element_json_repr(val)

            return out_json

    NewStruct.__name__ = type_name

    instance = NewStruct()

    for key, value in list(parsed_dict.items()):
        setattr(instance, key, value)

    # Set an internal attribute so that we know this struct was made by bread
    setattr(instance, "__baked_by_bread__", True)

    return instance

def write_from_parsed(writer, obj, spec, **kwargs):
    def handle_function(parse_function, options):
        parse_function(WRITE, writer, None, **options)

    def handle_field(field_name, parse_function, options):
        field_value = getattr(obj, field_name)

        if type(parse_function) == list:
            write_from_parsed(writer, field_value, parse_function, **options)
        else:
            parse_function(WRITE, writer, field_value, **options)

    def handle_conditional(
            conditional_field_name, conditional_clauses, spec_deque):
        conditional_val = getattr(obj, conditional_field_name)
        condition_spec = conditional_clauses[conditional_val]

        for spec_item in reversed(condition_spec):
            spec_deque.appendleft(spec_item)

    process_spec(spec, handle_function, handle_field, handle_conditional)

def write(parsed_obj, spec, filename=None):
    if filename is not None:
        fp = open(filename, 'wb')
    else:
        fp = ByteArrayStream()

    writer = BitwiseWriter(fp)

    write_from_parsed(writer, parsed_obj, spec)
    writer.close()

    if filename is None:
        return fp.array

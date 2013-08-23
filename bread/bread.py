import StringIO, types, struct, collections, functools
from bitstring import ConstBitStream

LITTLE_ENDIAN = 0
BIG_ENDIAN = 1
CONDITIONAL = 2

def parse(data_source, spec, type_name='bread_struct'):
    if type(data_source) == str:
        reader = ConstBitStream(bytes=data_source)
    else:
        reader = ConstBitStream(data_source)

    return parse_from_reader(reader, spec, type_name)

def parse_from_reader(reader, spec, type_name='bread_struct', **kwargs):
    offsets = {}
    keys = []
    length = 0
    parsed_dict = {}

    start_reader_offset = reader.pos

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
            spec_line(reader, **global_options)
        elif len(spec_line) == 1:
            # Spec lines of length 1 are assumed to be functions, which are
            # treated the same as before
            parse_function = spec_line[0]
            parse_function(reader, **global_options)
        elif spec_line[0] == CONDITIONAL:
            # Push appropriate conditional spec on the front of the current
            # one so that it will be evaluated next

            conditional_val = parsed_dict[spec_line[1]]

            condition_spec = spec_line[2][conditional_val]

            spec.extendleft(condition_spec)
        else:
            field_name = spec_line[0]
            parse_function = spec_line[1]
            options = global_options

            if len(spec_line) == 3:
                options = global_options.copy()
                options.update(spec_line[2])

            if "str_format" in options:
                formatter = options["str_format"]
            else:
                formatter = str

            keys.append((field_name, formatter))

            offsets[field_name] = reader.pos

            if type(parse_function) == list:
                val = parse_from_reader(reader, parse_function, **options)
            else:
                val = parse_function(reader, **options)

            if val is not None:
                parsed_dict[field_name] = val

    parsed_dict["__offsets__"] = type('bread_struct_offsets', (object, ),
                                      offsets)
    parsed_dict["_LENGTH"] = reader.pos - start_reader_offset

    def my_length(self):
        return self._LENGTH

    def my_print(self):
        string = ""

        for key, formatter in keys:
            string += "%s: %s\n" % (key, formatter(getattr(self, key)))

        return string

    parsed_type = type(type_name, (object,), parsed_dict)

    parsed_type.__len__ = types.MethodType(
        my_length, parsed_type, parsed_type.__class__)
    parsed_type.__str__ = types.MethodType(
        my_print, parsed_type, parsed_type.__class__)

    return parsed_type()

def intX(length, signed = False):
    def integer_type(reader, endianness = LITTLE_ENDIAN, offset = 0, **kwargs):
        if signed:
            format_string = 'int'
        else:
            format_string = 'uint'

        if length % 8 == 0:
            if endianness == LITTLE_ENDIAN:
                format_string += 'le'
            else:
                format_string += 'be'

        format_string += ':%d' % (length)

        return reader.read(format_string)

    return integer_type

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

def string(length, **kwargs):
    def string_parser(reader, **kwargs):
        return struct.unpack(
            "%ds" % (length), reader.read(length * 8).tobytes())[0]

    return string_parser

def boolean(reader, **kwargs):
    return reader.read(1).bool

def padding(length):
    def pad_parser(reader, **kwargs):
        # Skip over bits
        reader.read(length)
        return None

    return pad_parser

def enum(length, values):
    subparser = intX(length=length, signed=False)

    def parser(reader, **kwargs):
        coded_value = subparser(reader)

        return values[coded_value]

    return parser

def array(length, substruct):
    if type(substruct) == list:
        # Passed a nested struct, which should be parsed according to its spec
        subparse_function = functools.partial(parse_from_reader, spec=substruct)
    else:
        # Passed a parsing function; should just return whatever that thing
        # parses
        subparse_function = substruct

    def parser(reader, **kwargs):
        substructs = []

        for i in xrange(length):
            substructs.append(subparse_function(reader))

        return substructs

    return parser

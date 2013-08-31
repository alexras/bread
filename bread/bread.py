import StringIO, types, struct, collections, functools
from bitstring import ConstBitStream, BitArray, pack

LITTLE_ENDIAN = 0
BIG_ENDIAN = 1
CONDITIONAL = 2

# Enumeration of different operations that field descriptors can perform
READ = 0
WRITE = 1

def parse(data_source, spec, type_name='bread_struct'):
    if type(data_source) == str:
        reader = ConstBitStream(bytes=data_source)
    elif type(data_source) == list:
        reader = ConstBitStream(bytes=data_source)
    else:
        reader = ConstBitStream(data_source)

    return parse_from_reader(reader, spec, type_name)

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
            except Exception, e:
                print "Error while processing %s: %s" % (spec_line, e)
                raise e
        elif len(spec_line) == 1:
            # Spec lines of length 1 are assumed to be functions, which are
            # treated the same as before
            try:
                handle_function(spec_line[0], global_options)
            except Exception, e:
                print "Error while processing %s: %s" % (spec_line, e)
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
            except Exception, e:
                print "Error while processing field '%s': %s" % (
                    field_name, e)
                raise e

def parse_from_reader(reader, spec, type_name='bread_struct', **kwargs):
    offsets = {}
    keys = []
    length = 0
    parsed_dict = {}

    start_reader_offset = reader.pos

    def handle_function(parse_function, options):
        parse_function(READ, reader, **options)

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
            val = parse_function(READ, reader, **options)

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

    for key, value in offsets.items():
        setattr(offsets_obj, key, value)

    parsed_dict["__offsets__"] = offsets_obj
    parsed_dict["_LENGTH"] = reader.pos - start_reader_offset

    class NewStruct(object):
        def __eq__(self, other):
            return self.__dict__ == other.__dict__

        def __ne__(self, other):
            return not self.__eq__(other)

        def __len__(self):
            return self._LENGTH

        def __str__(self):
            string = ""

            for key, formatter in keys:
                string += "%s: %s\n" % (key, formatter(getattr(self, key)))

            return string

        def __getattr__(self, name):
            raise ValueError("No known field '%s'" % (name))

    NewStruct.__name__ = type_name

    instance = NewStruct()

    for key, value in parsed_dict.items():
        setattr(instance, key, value)

    return instance

def write_from_parsed(obj, spec, **kwargs):
    output_data = BitArray()

    def handle_function(parse_function, options):
        output_data.append(parse_function(WRITE, None, **options))

    def handle_field(field_name, parse_function, options):
        field_value = getattr(obj, field_name)

        if type(parse_function) == list:
            output_data.append(
                write_from_parsed(field_value, parse_function, **options))
        else:
            output_data.append(parse_function(WRITE, field_value, **options))

    def handle_conditional(
            conditional_field_name, conditional_clauses, spec_deque):
        conditional_val = getattr(obj, conditional_field_name)
        condition_spec = conditional_clauses[conditional_val]

        for spec_item in reversed(condition_spec):
            spec_deque.appendleft(spec_item)

    process_spec(spec, handle_function, handle_field, handle_conditional)

    return output_data

def write(parsed_obj, spec, filename=None):
    output_data = write_from_parsed(parsed_obj, spec).tobytes()

    if filename is not None:
        with open(filename, 'wb') as fp:
            fp.write(output_data)
    else:
        return bytearray(output_data)

def field_descriptor(read_fn, write_fn, length):
    # For reads, 'target' is a reader. For writes, it's a value to write.
    def catchall_fn(_operation, _target, **kwargs):
        if _operation == READ:
            return read_fn(_target, **kwargs)
        elif _operation == WRITE:
            if _target is None:
                assert length is not None, (
                    "Field is null, but I can't determine its length for "
                    "padding")
                return pack('pad:%d' % (length))
            else:
                return write_fn(_target, **kwargs)

    return catchall_fn

def intX(length, signed = False):
    def _gen_format_string(endianness):
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
        return format_string

    def integer_type_read(reader, endianness = LITTLE_ENDIAN, offset = 0,
                          **kwargs):
        format_string = _gen_format_string(endianness)
        return reader.read(format_string) + offset

    def integer_type_write(val, endianness = LITTLE_ENDIAN,
                           offset = 0, **kwargs):
        format_string = _gen_format_string(endianness)

        return pack(format_string, val - offset)

    return field_descriptor(integer_type_read, integer_type_write, length)

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
    string_length = length * 8

    def string_parser(reader, **kwargs):
        return struct.unpack(
            "%ds" % (length), reader.read(string_length).tobytes())[0]

    def string_writer(value, **kwargs):
        return pack("bytes:%d" % (length), value)

    return field_descriptor(string_parser, string_writer, length * 8)

def _boolean_reader(reader, **kwargs):
    return reader.read(1).bool

def _boolean_writer(value, **kwargs):
    return pack('bool', value)

boolean = field_descriptor(_boolean_reader, _boolean_writer, 1)

def padding(length):
    def pad_parser(reader, **kwargs):
        # Skip over bits
        reader.read(length)
        return None

    def pad_writer(value, **kwargs):
        return pack("pad:%n" % (length))

    return field_descriptor(pad_parser, pad_writer, length)

def enum(length, values, default=None):
    subparser = intX(length=length, signed=False)

    def parser(reader, **kwargs):
        coded_value = subparser(READ, reader)

        if coded_value not in values:
            if default is not None:
                return default
            else:
                raise ValueError(
                    "Value '%s' does not correspond to a valid enum value" %
                    (coded_value))
        else:
            return values[coded_value]

    def writer(value, **kwargs):
        for coded_value in values:
            if values[coded_value] == value:
                return subparser(WRITE, coded_value)

        return None

    return field_descriptor(parser, writer, length)

def array(length, substruct):
    def parser(reader, **kwargs):
        if type(substruct) == list:
            # Passed a nested struct, which should be parsed according to its
            # spec
            subparse_function = functools.partial(
                parse_from_reader, reader=reader, spec=substruct)
        else:
            # Passed a parsing function; should just return whatever that thing
            # parses
            subparse_function = functools.partial(
                substruct, _operation=READ, _target=reader)

        substructs = []

        for i in xrange(length):
            substructs.append(subparse_function(**kwargs))

        return substructs

    def writer(values, **kwargs):
        total_bitstr = BitArray()

        for value in values:
            if type(substruct) == list:
                subparse_function = functools.partial(
                    write_from_parsed, obj=value, spec=substruct)
            else:
                subparse_function = functools.partial(
                    substruct, _operation=WRITE, _target=value)

            total_bitstr = total_bitstr + subparse_function(**kwargs)

        return total_bitstr

    # Returning None for length, since we can't know what the length is going
    # to be without looking ahead
    return field_descriptor(parser, writer, None)

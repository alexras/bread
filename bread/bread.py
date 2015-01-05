import StringIO, types, struct, collections, functools, json
from bitstring import ConstBitStream, pack

LITTLE_ENDIAN = 0
BIG_ENDIAN = 1
CONDITIONAL = 2

COMPACT_FORMAT_STRINGS = {
    8: 'b',
    16: 'h',
    32: 'l',
    64: 'q'
}

KEEP_LEFT = [
    0b00000000,
    0b10000000,
    0b11000000,
    0b11100000,
    0b11110000,
    0b11111000,
    0b11111100,
    0b11111110,
    0b11111111]

KEEP_RIGHT = [
    0b00000000,
    0b00000001,
    0b00000011,
    0b00000111,
    0b00001111,
    0b00011111,
    0b00111111,
    0b01111111,
    0b11111111]

def mask(x, offset, length):
    """
    Masks off a portion of the byte starting at `offset` and extending for
    `length` bits.
    """
    return (x & KEEP_RIGHT[8 - offset]) & KEEP_LEFT[min(offset + length, 8)]

def rightshift(bytelist, length, offset):
    """
    Shift every byte in `bytelist` to the right by `offset` and return the
    new bytelist as a bytearray.
    """
    prev_byte = None

    # Only return the bytes that actually contain data (to avoid returning
    # extra 0 bytes unnecessarily)
    bytes_to_keep = 0

    shifted_bytes = []

    # Handle the easier base-cases (more than a whole byte of shift, or no
    # shift at all)
    while offset >= 8:
        shifted_bytes.append(0)
        offset -= 8
        bytes_to_keep += 1

    # Round up to the nearest byte
    bytes_to_keep += (offset + length + 7) / 8

    if offset == 0:
        shifted_bytes.extend(bytelist)
        return shifted_bytes

    next_byte = 0

    for b in bytelist:
        first_bits = mask(b, 0, 8 - offset)
        last_bits = mask(b, 8 - offset, offset)

        shifted_bytes.append( (first_bits >> offset) | next_byte)
        next_byte = last_bits << (8 - offset)

    shifted_bytes.append(next_byte)

    return shifted_bytes[:bytes_to_keep]

class BitwiseWriter(object):
    def __init__(self, stream):
        self.bits_written = 0
        self.last_byte = 0b00000000
        self.fp = stream

    def write(self, data, length_in_bits):
        py_len = len(data)
        bread_len_bytes = (length_in_bits + 7) / 8

        assert py_len == bread_len_bytes, (
            "Length of data in Python (%d) doesn't "
            "match its length in bytes (%d)" % (py_len, bread_len_bytes))

        if len(data) == 0:
            return

        # If we've got some bits left over from the last write, we'll need to
        # shift the data over and push those last bits into the front of the
        # write stream
        right_shift_amt = self.bits_written % 8

        if right_shift_amt > 0:
            shifted_data = rightshift(data, length_in_bits, right_shift_amt)
            shifted_data[0] = shifted_data[0] | self.last_byte
        else:
            shifted_data = data

        leftover_bits = (self.bits_written + length_in_bits) % 8

        # If data doesn't end on a clean byte boundary,
        if leftover_bits != 0:
            self.last_byte = shifted_data.pop()

        if len(shifted_data) > 0:
            self.fp.write(shifted_data)

        self.bits_written += length_in_bits

    def close(self):
        if self.bits_written % 8 != 0:
            self.fp.write(bytearray([self.last_byte]))

        self.fp.close()

class ByteArrayStream(object):
    def __init__(self):
        self.array = bytearray()

    def write(self, x):
        if type(x) in [list, bytearray]:
            self.array.extend(x)
        else:
            self.array.append(x)

    def close(self):
        pass

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

    for key, value in offsets.items():
        setattr(offsets_obj, key, value)

    parsed_dict["__offsets__"] = offsets_obj
    parsed_dict["_LENGTH"] = reader.pos - start_reader_offset

    class NewStruct(object):
        def __eq__(self, other):
            for key in self.__dict__.keys():
                print key
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
            raise ValueError("No known field '%s'" % (name))

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
                    out_json[key] = map(self.__element_json_repr, val)
                else:
                    out_json[key] = self.__element_json_repr(val)

            return out_json

    NewStruct.__name__ = type_name

    instance = NewStruct()

    for key, value in parsed_dict.items():
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

def field_descriptor(read_fn, write_fn, length):
    # For reads, 'target' is a reader and 'data' is None. For writes, 'target'
    # is a writer and 'data' is the value to write.
    def catchall_fn(_operation, _target, _data, **kwargs):
        if _operation == READ:
            return read_fn(_target, **kwargs)
        elif _operation == WRITE:
            if _data is None:
                assert length is not None, (
                    "Field is null, but I can't determine its length for "
                    "padding")
                return make_pad_writer(length)(_target, _data)
            else:
                return write_fn(_target, _data, **kwargs)

    return catchall_fn

def intX(length, signed = False):
    simple_length = length in COMPACT_FORMAT_STRINGS

    def _gen_format_string(endianness):
        if simple_length:
            if endianness == LITTLE_ENDIAN:
                format_string = '<'
            else:
                format_string = '>'

            format_character = COMPACT_FORMAT_STRINGS[length]

            if not signed:
                format_character = format_character.upper()

            format_string += format_character
        else:
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

    format_strings = {
        LITTLE_ENDIAN: _gen_format_string(LITTLE_ENDIAN),
        BIG_ENDIAN: _gen_format_string(BIG_ENDIAN)
    }

    def integer_type_read(reader, endianness = LITTLE_ENDIAN, offset = 0,
                          **kwargs):
        return reader.read(format_strings[endianness]) + offset

    def integer_type_write(writer, val, endianness = LITTLE_ENDIAN,
                           offset = 0, **kwargs):
        if simple_length:
            bytes_to_write = bytearray(
                struct.pack(format_strings[endianness], val - offset))
        else:
            bytes_to_write = bytearray(
                pack(format_strings[endianness], val - offset).tobytes())

        writer.write(bytes_to_write, length)


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

    def string_writer(writer, value, **kwargs):
        writer.write(bytearray(value.encode("utf-8")), string_length)

    return field_descriptor(string_parser, string_writer, length * 8)

def _boolean_reader(reader, **kwargs):
    return reader.read(1).bool

def _boolean_writer(writer, value, **kwargs):
    if value:
        bool_as_int = 0b10000000
    else:
        bool_as_int = 0

    writer.write([bool_as_int], 1)

boolean = field_descriptor(_boolean_reader, _boolean_writer, 1)

def make_pad_writer(length):
    def pad_writer(writer, value, **kwargs):
        writer.write(bytearray([0] * ((length + 7) / 8)), length)

    return pad_writer

def padding(length):
    def pad_parser(reader, **kwargs):
        # Skip over bits
        reader.read(length)
        return None

    return field_descriptor(pad_parser, make_pad_writer(length), length)

def enum(length, values, default=None):
    subparser = intX(length=length, signed=False)

    def parser(reader, **kwargs):
        coded_value = subparser(READ, reader, None)

        if coded_value not in values:
            if default is not None:
                return default
            else:
                raise ValueError(
                    "Value '%s' does not correspond to a valid enum value" %
                    (coded_value))
        else:
            return values[coded_value]

    def writer(writer, value, **kwargs):
        for coded_value in values:
            if values[coded_value] == value:
                subparser(WRITE, writer, coded_value)
                break

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
                substruct, _operation=READ, _target=reader, _data=None)

        substructs = []

        for i in xrange(length):
            substructs.append(subparse_function(**kwargs))

        return substructs

    def writer(writer, values, **kwargs):
        format_string_pieces = []
        data_values = []

        for value in values:
            if type(substruct) == list:
                subparse_function = functools.partial(
                    write_from_parsed, writer=writer, obj=value, spec=substruct)
            else:
                subparse_function = functools.partial(
                    substruct, _operation=WRITE, _target=writer, _data=value)

            subparse_function(**kwargs)


    # Returning None for length, since we can't know what the length is going
    # to be without looking ahead
    return field_descriptor(parser, writer, None)

def _append_compressed_piece(piece, count, compressed_pieces):
    if piece[0] in ('<', '>'):
        if count > 1:
            compressed_pieces.append(piece[0] + str(count) + piece[-1])
        else:
            compressed_pieces.append(piece)
    else:
        for i in xrange(count):
            compressed_pieces.append(piece)


def compress_format_string(pieces):
    prev_piece = None
    prev_count = 0

    compressed_pieces = []

    for piece in pieces:
        if piece[0] in ('<', '>') and len(piece) > 2:
            cur_piece = piece[0] + piece[-1]
            cur_count = int(piece[1:-1])
        else:
            cur_piece = piece
            cur_count = 1

        if cur_piece == prev_piece:
            prev_count += cur_count
        else:
            if prev_piece is not None:
                _append_compressed_piece(
                    prev_piece, prev_count, compressed_pieces)

            prev_piece = cur_piece
            prev_count = cur_count

    if prev_piece is not None:
        _append_compressed_piece(prev_piece, prev_count, compressed_pieces)

    return compressed_pieces

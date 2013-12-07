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
            self.fp.write(self.last_byte)

        self.fp.close()

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

def write_from_parsed(obj, spec, **kwargs):
    output_format_string_pieces = []
    output_values = []

    def add_to_output(partial_output):
        format_string_pieces, values = partial_output
        output_format_string_pieces.extend(format_string_pieces)
        output_values.extend(values)

    def handle_function(parse_function, options):
        add_to_output(parse_function(WRITE, None, **options))

    def handle_field(field_name, parse_function, options):
        field_value = getattr(obj, field_name)

        if type(parse_function) == list:
            field_output = write_from_parsed(
                field_value, parse_function, **options)

            add_to_output(field_output)
        else:
            field_output = parse_function(WRITE, field_value, **options)

            add_to_output(field_output)

    def handle_conditional(
            conditional_field_name, conditional_clauses, spec_deque):
        conditional_val = getattr(obj, conditional_field_name)
        condition_spec = conditional_clauses[conditional_val]

        for spec_item in reversed(condition_spec):
            spec_deque.appendleft(spec_item)

    process_spec(spec, handle_function, handle_field, handle_conditional)

    return output_format_string_pieces, output_values

def write(parsed_obj, spec, filename=None):
    pack_string_pieces, output_values = write_from_parsed(parsed_obj, spec)

    output_data = pack(', '.join(pack_string_pieces),
                       *output_values).tobytes()

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
                return (['pad:%d' % (length)], [])
            else:
                return write_fn(_target, **kwargs)

    return catchall_fn

def intX(length, signed = False):
    def _gen_format_string(endianness):
        if length in COMPACT_FORMAT_STRINGS:
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

    def integer_type_write(val, endianness = LITTLE_ENDIAN,
                           offset = 0, **kwargs):
        return ([format_strings[endianness]], [val - offset])

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
        return (["bytes:%d" % (length)], [value])

    return field_descriptor(string_parser, string_writer, length * 8)

def _boolean_reader(reader, **kwargs):
    return reader.read(1).bool

def _boolean_writer(value, **kwargs):
    return (['bool'], [value])

boolean = field_descriptor(_boolean_reader, _boolean_writer, 1)

def padding(length):
    def pad_parser(reader, **kwargs):
        # Skip over bits
        reader.read(length)
        return None

    def pad_writer(value, **kwargs):
        return (["pad:%n" % (length)], [])

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
        format_string_pieces = []
        data_values = []

        for value in values:
            if type(substruct) == list:
                subparse_function = functools.partial(
                    write_from_parsed, obj=value, spec=substruct)
            else:
                subparse_function = functools.partial(
                    substruct, _operation=WRITE, _target=value)

            subparse_pieces, subparse_values = subparse_function(**kwargs)

            format_string_pieces.extend(subparse_pieces)
            data_values.extend(subparse_values)

        format_string_pieces = compress_format_string(format_string_pieces)

        return (format_string_pieces, data_values)

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

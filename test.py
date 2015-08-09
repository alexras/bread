#!/usr/bin/env python

import struct, sys, pprint, unittest, itertools, tempfile, os, json

from nose.tools import assert_equal, assert_not_equal, assert_true, \
    assert_false, assert_raises, raises

import bread as b

import bitstring

# Shared structs for bread struct test

test_struct = [
    {
        "endianness": b.BIG_ENDIAN
    },
    ("flag_one", b.boolean),
    ("flag_two", b.boolean),
    ("flag_three", b.boolean),
    ("flag_four", b.boolean),
    ("first", b.uint8),
    (b.padding(2),),
    b.padding(2),
    ("blah", b.uint16),
    ("second", b.int64),
    ("third", b.uint64),
    ("fourth", b.int8)
]

test_array_struct = [
    {
        "endianness": b.BIG_ENDIAN
    },
    ("first", b.uint8),
    ("flags", b.array(8, b.boolean)),
    ("last", b.uint8)]

nested_array_struct = [
    {
        "endianness": b.BIG_ENDIAN
    },
    ("first", b.uint8),
    ("matrix", b.array(3, b.array(3, b.uint8))),
    ("last", b.uint8)
]

simple_struct = [
    ("length", b.uint8),
    ("ok", b.boolean)
]

offset_struct = [
    ("length", b.uint8, {"offset": 1})
]

deeply_nested_struct = [
    {
        "endianness": b.BIG_ENDIAN
    },
    ("ubermatrix", b.array(3, nested_array_struct)),
    ("dummy", simple_struct)
]

conditional_test = [
    ("qux", b.boolean),
    (b.CONDITIONAL, "qux", {
        False: [("fooz", b.byte), ("barz", b.byte)],
        True: [("frooz", b.nibble), ("quxz", b.byte)]
    })
]

as_native_struct = [
    {
        "endianness": b.BIG_ENDIAN
    },
    ("ubermatrix", b.array(3, nested_array_struct)),
    ("dummy", simple_struct),
    b.padding(7)
]


def test_simple_struct():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec=test_struct)

    assert_equal(test.__offsets__.flag_one, 0)
    assert_equal(test.__offsets__.flag_two, 1)
    assert_equal(test.__offsets__.flag_three, 2)
    assert_equal(test.__offsets__.flag_four, 3)
    assert_equal(test.__offsets__.first, 4)
    assert_equal(test.__offsets__.blah, 16)
    assert_equal(test.__offsets__.second, 32)
    assert_equal(test.__offsets__.third, 96)
    assert_equal(test.__offsets__.fourth, 160)

    assert_equal(len(test), 168)

    assert_equal(test.flag_one, True)
    assert_equal(test.flag_two, False)
    assert_equal(test.flag_three, True)
    assert_equal(test.flag_four, False)
    assert_equal(test.first, 0xfb)
    assert_equal(test.blah, 0xdddd)

    assert_equal(test.second, -57)
    assert_equal(test.third, 90)
    assert_equal(test.fourth, 0)

    output_data = b.write(test, test_struct)

    assert_equal(output_data, data)

    expected_json_struct = {
        "flag_one": True,
        "flag_two": False,
        "flag_three": True,
        "flag_four": False,
        "first": 0xfb,
        "blah": 0xdddd,
        "second": -57,
        "third": 90,
        "fourth": 0
    }

    assert_equal(json.loads(test.as_json()), expected_json_struct)


def test_write_intX():
    ints_struct = [
        ("off_by_one", b.uint8, {"offset": 1}),
        ("unsigned_int", b.uint16),
        ("signed_int", b.int8)
    ]

    data = bytearray([5, 0xba, 0xbd, 0xed])
    parsed = b.parse(data, ints_struct)

    assert_equal(parsed.off_by_one, 6)
    assert_equal(parsed.unsigned_int, 0xbdba)
    assert_equal(parsed.signed_int, -19)

    parsed.off_by_one = 9
    parsed.unsigned_int = 0xcbab
    parsed.signed_int = -7

    output = b.write(parsed)

    assert_equal(output, bytearray([8, 0xab, 0xcb, 0xf9]))


def test_updates_do_not_leak():
    data = struct.pack(">IqQb", 0xafb3dddd, -57, 90, 0)
    data2 = struct.pack(">IqQb", 0x1de0fafe, 24, 999999, 1)

    test = b.parse(data, test_struct)

    test2 = b.parse(data2, test_struct)

    # test2's offsets should be the same as test's

    assert_equal(test2.__offsets__.flag_one, 0)
    assert_equal(test2.__offsets__.flag_two, 1)
    assert_equal(test2.__offsets__.flag_three, 2)
    assert_equal(test2.__offsets__.flag_four, 3)
    assert_equal(test2.__offsets__.first, 4)
    assert_equal(test2.__offsets__.blah, 16)
    assert_equal(test2.__offsets__.second, 32)
    assert_equal(test2.__offsets__.third, 96)
    assert_equal(test2.__offsets__.fourth, 160)

    assert_equal(len(test2), 168)

    assert_equal(test2.flag_one, False)
    assert_equal(test2.flag_two, False)
    assert_equal(test2.flag_three, False)
    assert_equal(test2.flag_four, True)
    assert_equal(test2.first, 0xde)
    assert_equal(test2.blah, 0xfafe)

    assert_equal(test2.second, 24)
    assert_equal(test2.third, 999999)
    assert_equal(test2.fourth, 1)

    # Updating test2 shouldn't impact test

    assert_equal(test.flag_one, True)
    assert_equal(test.flag_two, False)
    assert_equal(test.flag_three, True)
    assert_equal(test.flag_four, False)
    assert_equal(test.first, 0xfb)
    assert_equal(test.blah, 0xdddd)

    assert_equal(test.second, -57)
    assert_equal(test.third, 90)
    assert_equal(test.fourth, 0)


def test_array():
    data = bytearray([0b11111111, 0b10010101, 0b00010001])

    array_test = b.parse(data, test_array_struct)

    assert_equal(array_test.__offsets__.first, 0)
    assert_equal(array_test.__offsets__.flags, 8)
    assert_equal(array_test.__offsets__.last, 16)

    assert_equal(len(array_test), 24)

    expected_flags = [True, False, False, True, False, True, False, True]

    assert_equal(array_test.flags, expected_flags)

    assert_equal(b.write(array_test, test_array_struct), data)


def test_nested_array():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])

    nested_test = b.parse(data, nested_array_struct)

    assert_equal(nested_test.__offsets__.first, 0)
    assert_equal(nested_test.__offsets__.matrix, 8)
    assert_equal(nested_test.__offsets__.last, 80)
    assert_equal(len(nested_test), 88)

    assert_equal(nested_test.first, 42)

    for i in range(9):
        assert_equal(nested_test.matrix[int(i / 3)][int(i % 3)], i)

    assert_equal(nested_test.last, 0xdb)

    assert_equal(b.write(nested_test, nested_array_struct), data)

    expected_json_struct = {
        "first": 42,
        "matrix": [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
        "last": 0xdb
    }

    assert_equal(json.loads(nested_test.as_json()), expected_json_struct)


def test_nested_struct():
    data = bitstring.BitArray(bytearray(range(34)))
    data.append('0b0')

    supernested_test = b.parse(data, deeply_nested_struct)

    assert_equal(supernested_test.__offsets__.ubermatrix, 0)
    assert_equal(supernested_test.__offsets__.dummy, 264)
    assert_equal(len(supernested_test), 273)

    assert_equal(len(supernested_test.ubermatrix), 3)
    assert_equal(sum(map(len, supernested_test.ubermatrix)), 264)

    current_byte = 0

    for substruct in supernested_test.ubermatrix:
        assert_equal(substruct.first, current_byte)
        current_byte += 1

        for i, j in itertools.product(range(3), range(3)):
            assert_equal(substruct.matrix[i][j], current_byte + i * 3 + j)

        current_byte += 9

        assert_equal(substruct.last, current_byte)
        current_byte += 1

    assert_equal(supernested_test.__offsets__.dummy, current_byte * 8)
    current_byte += 1
    assert_equal(supernested_test.dummy.ok, False)

    assert_equal(b.write(supernested_test, deeply_nested_struct),
                 bytearray(list(range(34)) + [0b0]))

    expected_json_struct = {
        "dummy": {
            "length": 33,
            "ok": False
        },
        "ubermatrix": [
            {
                "first": 0,
                "matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                "last": 10
            },
            {
                "first": 11,
                "matrix": [[12, 13, 14], [15, 16, 17], [18, 19, 20]],
                "last": 21
            },
            {
                "first": 22,
                "matrix": [[23, 24, 25], [26, 27, 28], [29, 30, 31]],
                "last": 32
            }
        ]
    }

    assert_equal(json.loads(supernested_test.as_json()), expected_json_struct)


def test_single_byte_fields():
    single_byte_fields_struct = [
        ("bit_0", b.bit),
        ("bit_1", b.bit),
        ("semi_nibble", b.semi_nibble),
        ("nibble", b.nibble)]

    data = bytearray([0b10110010])

    test = b.parse(data, single_byte_fields_struct)

    assert_equal(test.bit_0, 1)
    assert_equal(test.bit_1, 0)
    assert_equal(test.semi_nibble, 0b11)
    assert_equal(test.nibble, 0b0010)

    assert_equal(b.write(test, single_byte_fields_struct), data)


def test_endianness():
    endianness_test = [
        ("big_endian", b.uint32, {"endianness": b.BIG_ENDIAN}),
        ("little_endian", b.uint32, {"endianness": b.LITTLE_ENDIAN}),
        ("default_endian", b.uint32)]

    data = bytearray([0x01, 0x02, 0x03, 0x04] * 3)

    test = b.parse(data, endianness_test)

    assert_equal(test.big_endian, 0x01020304)
    assert_equal(test.little_endian, 0x04030201)
    assert_equal(hex(test.default_endian), hex(test.little_endian))

    assert_equal(b.write(test, endianness_test), data)


def test_conditional():
    true_data = bitstring.BitArray(bytearray([0b11001010, 0b11101000]))
    true_data.append('0b0')

    true_test = b.parse(true_data, conditional_test)

    assert_equal(true_test.qux, True)
    assert_true(hasattr(true_test, "frooz"))
    assert_false(hasattr(true_test, "fooz"))
    assert_equal(true_test.frooz, 0b1001)
    assert_equal(true_test.quxz, 0b01011101)

    assert_equal(b.write(true_test, conditional_test),
                 bytearray([0b11001010, 0b11101000, 0]))

    false_data = bitstring.BitArray(
        bytearray([0b01001000, 0b10000000]))
    false_data.append('0b1')

    false_test = b.parse(false_data, conditional_test)

    assert_equal(false_test.qux, False)
    assert_true(hasattr(false_test, "fooz"))
    assert_false(hasattr(false_test, "frooz"))
    assert_equal(false_test.fooz, 0b10010001)
    assert_equal(false_test.barz, 1)

    assert_equal(b.write(false_test, conditional_test),
                 bytearray([0b01001000, 0b10000000, 0b10000000]))


def test_conditional_as_native():
    true_data = bitstring.BitArray(bytearray([0b11001010, 0b11101000]))
    true_data.append('0b0')

    test_struct = b.parse(true_data, conditional_test)

    assert_equal(test_struct.as_native(), {
        'qux': True,
        'frooz': 0b1001,
        'quxz': 0b01011101
    })

    test_struct.qux = False

    assert_equal(test_struct.as_native(), {
        'qux': False,
        'fooz': 0b10010101,
        'barz': 0b11010000
    })


def test_conditional_set():
    true_data = bitstring.BitArray(bytearray([0b11001010, 0b11101000]))
    true_data.append('0b0')

    test_struct = b.parse(true_data, conditional_test)

    assert_equal(test_struct.frooz, 0b1001)
    assert_equal(test_struct.quxz, 0b01011101)
    assert_true(test_struct.qux)

    assert_false(hasattr(test_struct, "fooz"))
    assert_false(hasattr(test_struct, "barz"))

    test_struct.qux = False

    assert_false(test_struct.qux)

    assert_equal(test_struct.fooz, 0b10010101)
    assert_equal(test_struct.barz, 0b11010000)

    assert_false(hasattr(test_struct, "frooz"))
    assert_false(hasattr(test_struct, "quxz"))

    test_struct.barz = 0b11101010

    written_bytes = b.write(test_struct)

    expected_bytes = bytearray([0b01001010, 0b11110101, 0b0])

    assert_equal(written_bytes, expected_bytes)


@raises(b.BadConditionalCaseError)
def test_conditional_bad_switch():
    test_struct = [
        ("cond", b.uint8),
        (b.CONDITIONAL, "cond", {
            1: [("foo", b.uint8)],
            2: [("foo", b.uint8)],
            4: [("foo", b.uint8)]
        })
    ]

    test_data = bytearray([3, 9])
    test_parsed = b.parse(test_data, test_struct)

    test_parsed.foo = 12


def test_as_native():
    data = bitstring.BitArray(bytearray(range(35)))

    supernested_test = b.parse(data, as_native_struct)

    assert_equal(supernested_test.as_native(), {
        'ubermatrix': [
            {
                'first': 0,
                'matrix': [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                'last': 10
            },
            {
                'first': 11,
                'matrix': [[12, 13, 14], [15, 16, 17], [18, 19, 20]],
                'last': 21
            },
            {
                'first': 22,
                'matrix': [[23, 24, 25], [26, 27, 28], [29, 30, 31]],
                'last': 32
            }
        ],
        'dummy': {
            'length': 33,
            'ok': False
        }
    })


def test_array_of_conditionals():
    test_struct = [
        ("cond", b.uint8),
        ("foos", b.array(3, (b.CONDITIONAL, "cond", {
            1: [("foo", b.nibble), b.padding(4)],
            2: [("bar", b.bit), b.padding(7)],
            4: [("baz", b.semi_nibble), b.padding(6)]
        })))
    ]

    test_data = bytearray([1, 0b10000101, 0b01010110, 0b11010101])

    test_parsed = b.parse(test_data, test_struct)

    assert_equal(test_parsed.cond, 1)
    assert_equal(test_parsed.foos[0].foo, 0b1000)
    assert_equal(test_parsed.foos[1].foo, 0b0101)
    assert_equal(test_parsed.foos[2].foo, 0b1101)

    test_parsed.cond = 4

    assert_equal(test_parsed.cond, 4)
    assert_equal(test_parsed.foos[0].baz, 0b10)
    assert_equal(test_parsed.foos[1].baz, 0b01)
    assert_equal(test_parsed.foos[2].baz, 0b11)


def test_field_properties_in_array():
    array_endian_test = [
        ("little_arr", b.array(3, b.uint16), {"endianness": b.LITTLE_ENDIAN}),
        ("big_arr", b.array(3, b.uint16), {"endianness": b.BIG_ENDIAN})
    ]

    data = bytearray([0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
                      0x01, 0x02, 0x03, 0x04, 0x05, 0x06])

    test = b.parse(data, array_endian_test)

    assert_equal(len(test.little_arr), 3)
    assert_equal(test.little_arr[0], 0x0201)
    assert_equal(test.little_arr[1], 0x0403)
    assert_equal(test.little_arr[2], 0x0605)

    assert_equal(len(test.big_arr), 3)
    assert_equal(test.big_arr[0], 0x0102)
    assert_equal(test.big_arr[1], 0x0304)
    assert_equal(test.big_arr[2], 0x0506)


@raises(ValueError)
def test_set_non_leaf_value_fails():
    struct_in_a_struct = [
        ("simple", [
            ("fooz", b.uint8),
            ("mooz", b.uint8),
            ("shooz", b.uint8)
        ])
    ]

    data = bitstring.BitArray(bytearray([1, 2, 3]))

    nested_set_test = b.parse(data, struct_in_a_struct)

    nested_set_test.simple = 5


def test_multiple_conditionals():
    test_struct = [
        ("cond", b.uint8),
        (b.CONDITIONAL, "cond", {
            1: [("foo", b.uint8)],
            2: [("foo", b.uint8)],
            4: [("foo", b.uint8)]
        }),
        (b.CONDITIONAL, "cond", {
            1: [("qux", b.uint8)],
            2: [("buzz", b.uint8)],
            4: [("fuzz", b.uint8)]
        })
    ]

    test_data = bytearray([1, 2, 4])
    test_parsed = b.parse(test_data, test_struct)

    assert_equal(test_parsed.foo, 2)
    assert_equal(test_parsed.qux, 4)


def test_set_sub_byte_intX():
    test_struct = [
        ("signed_nibble", b.intX(4, signed=True)),
        ("bit1", b.bit),
        ("bit2", b.bit),
        ("seminibble", b.semi_nibble)
    ]

    test_data = bytearray([0xdb])

    test_parsed = b.parse(test_data, test_struct)
    assert_equal(test_parsed.signed_nibble, -3)

    test_parsed.signed_nibble = -6
    test_parsed.bit1 = 0
    test_parsed.seminibble = 2

    assert_equal(bytearray([0xa2]), b.write(test_parsed))


def test_parse_str():
    test_struct = [
        ("str", b.string(13))
    ]

    test_str = str("gabbagabbahey")

    test_parsed = b.parse(test_str, test_struct)

    assert_equal(test_parsed.str.decode('utf-8'), "gabbagabbahey")


def test_str():
    str_test = [("msg", b.string(5))]

    data = bytearray([0x68, 0x65, 0x6c, 0x6c, 0x6f])
    result = b.parse(data, str_test)
    assert_equal(result.msg.decode('utf-8'), "hello")

    assert_equal(b.write(result, str_test), data)


def test_str_unicode():
    str_test = [("msg", b.string(5))]

    data = bytearray([104, 101, 108, 108, 111])
    result = b.parse(data, str_test)

    assert_equal(result.msg.decode('utf-8'), "hello")
    assert_equal(b.write(result, str_test), data)

    result.msg = "abate"

    output_data = b.write(result, str_test)

    edited_result = b.parse(output_data, str_test)

    assert_equal(result.msg, "abate")


def test_enum():
    enum_test = [
        ("suit", b.enum(8, {
            0: "diamonds",
            1: "hearts",
            2: "spades",
            3: "clubs"
        }))]

    for value, suit in zip(
            list(range(4)), ["diamonds", "hearts", "spades", "clubs"]):
        data = bytearray([value])
        result = b.parse(data, enum_test)

        assert_equal(result.suit, suit)
        assert_equal(b.write(result, enum_test), data)

    spades_test = b.parse([2], enum_test)
    spades_test.suit = "clubs"

    assert_equal(bytearray([3]), b.write(spades_test))

    def get_data_field():
        data = bytearray([42])
        result = b.parse(data, enum_test)
        result.suit

    assert_raises(ValueError, get_data_field)


def test_enum_default():
    enum_test = [
        ("suit", b.enum(8, {
            0: "diamonds",
            1: "hearts",
            2: "spades",
            3: "clubs"
        }, default="joker"))]

    data = bytearray([42])
    result = b.parse(data, enum_test)

    assert_equal(result.suit, "joker")

    data = bytearray([2])
    result = b.parse(data, enum_test)

    assert_equal(result.suit, "spades")


@raises(ValueError)
def test_enum_set_invalid_value():
    enum_test = [
        ("suit", b.enum(8, {
            0: "diamonds",
            1: "hearts",
            2: "spades",
            3: "clubs"
        }, default="joker"))]

    data = bytearray([1])
    parsed = b.parse(data, enum_test)

    assert_equal("hearts", parsed.suit)

    parsed.suit = "skulls"


def test_conditional_on_non_integer_enum():
    enum_test = [
        ("instrument_type", b.enum(8, {
            0: "pulse",
            1: "wave",
            2: "kit",
            3: "noise"
        })),
        (b.CONDITIONAL, "instrument_type", {
            "pulse": [("pulse_foo", b.uint8)],
            "wave": [("wave_foo", b.uint8)],
            "kit": [("kit_foo", b.uint8)],
            "noise": [("noise_foo", b.uint8)]
        })]

    pulse_test = bytearray([0, 19])

    pulse = b.parse(pulse_test, enum_test)

    assert_equal(pulse.instrument_type, "pulse")
    assert_equal(pulse.pulse_foo, 19)

    assert_equal(b.write(pulse, enum_test), pulse_test)

    wave_test = bytearray([1, 65])

    wave = b.parse(wave_test, enum_test)

    assert_equal(wave.instrument_type, "wave")
    assert_equal(wave.wave_foo, 65)

    assert_equal(b.write(wave, enum_test), wave_test)

    kit_test = bytearray([2, 9])

    kit = b.parse(kit_test, enum_test)

    assert_equal(kit.instrument_type, "kit")
    assert_equal(kit.kit_foo, 9)

    assert_equal(b.write(kit, enum_test), kit_test)

    noise_test = bytearray([3, 17])

    noise = b.parse(noise_test, enum_test)

    assert_equal(noise.instrument_type, "noise")
    assert_equal(noise.noise_foo, 17)

    assert_equal(b.write(noise, enum_test), noise_test)


def test_non_powers_of_eight_intX():
    intX_test = [
        ("unsigned_10b", b.intX(10, False)),
        ("unsigned_14b", b.intX(14, False)),
        ("signed_20b", b.intX(20, True)),
        ("signed_4b", b.intX(4, True)),
    ]

    in_bytes = bytearray([
        0b11010101, 0b11101010, 0b00110101, 0b11010101, 0b11101010, 0b00110101])

    result = b.parse(in_bytes, intX_test)

    assert_equal(result.unsigned_10b, 0b1101010111)
    assert_equal(result.unsigned_14b, 0b10101000110101)
    assert_equal(result.signed_20b, - 0b101010000101011101)
    assert_equal(result.signed_4b, 0b0101)

    assert_equal(b.write(result, intX_test), in_bytes)


def test_read_modify_write():
    data = bitstring.BitArray(bytearray(range(34)))
    data.append('0b0')

    supernested_test = b.parse(data, deeply_nested_struct)

    assert_equal(supernested_test.ubermatrix[1].matrix[2][1], 19)

    supernested_test.ubermatrix[1].matrix[2][1] = 42
    assert_equal(supernested_test.ubermatrix[1].matrix[2][1], 42)

    written_data = b.write(supernested_test, deeply_nested_struct)

    re_read_data = b.parse(written_data, deeply_nested_struct)

    assert_equal(re_read_data.ubermatrix[1].matrix[2][1], 42)


def test_read_modify_write_with_offset():
    data = bytearray([4])

    parsed = b.parse(data, offset_struct)
    assert_equal(parsed.length, 5)

    output = b.write(parsed, offset_struct)
    assert_equal(output, data)

    parsed.length = 10

    output = b.write(parsed, offset_struct)

    assert_equal(output[0], 9)


def test_file_io():
    data = bytearray(list(range(36)))

    supernested_test = b.parse(data, deeply_nested_struct)

    (handle, file_path) = tempfile.mkstemp()

    try:
        b.write(supernested_test, deeply_nested_struct, filename=file_path)

        with open(file_path, 'rb') as fp:
            supernested_test_from_file = b.parse(fp, deeply_nested_struct)

        for i, j, k in itertools.product(range(3), range(3), range(3)):
            assert_equal(supernested_test_from_file.ubermatrix[i].matrix[j][k],
                         supernested_test.ubermatrix[i].matrix[j][k])
    finally:
        os.close(handle)
        os.unlink(file_path)


def test_comparison():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    obj_1 = b.parse(data, spec=test_struct)
    obj_2 = b.parse(data, spec=test_struct)

    assert_equal(obj_1, obj_2)

    obj_2.flag_four = not obj_1.flag_four

    assert_not_equal(obj_1, obj_2)

    obj_2.flag_four = obj_1.flag_four

    assert_equal(obj_1, obj_2)


@raises(AttributeError)
def test_invalid_field_get_raises():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec=test_struct)

    test.missingfield


@raises(AttributeError)
def test_invalid_field_set_raises():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec=test_struct)

    test.missingfield = 12


@raises(ValueError)
def test_too_small_struct_fails():
    data = "X".encode('utf-8')
    b.parse(data, spec=simple_struct)


@raises(ValueError)
def test_bad_type_fails():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec=test_struct)
    test.flag_four = 50


def test_compare_struct_to_nonstruct_returns_false():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec=test_struct)

    assert_not_equal(test, 75)


@raises(ValueError)
def test_set_array_to_nonarray_fails():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])

    nested_test = b.parse(data, nested_array_struct)

    nested_test.matrix = 46


def test_set_array_to_list():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])
    nested_test = b.parse(data, nested_array_struct)

    nested_test.matrix = [[2, 4, 6], [8, 10, 12], [14, 16, 18]]

    output_bytes = b.write(nested_test)

    assert_equal(output_bytes, bytearray(
        [42, 2, 4, 6, 8, 10, 12, 14, 16, 18, 0xdb]))

    nested_test.matrix[1] = [9, 8, 7]

    output_bytes = b.write(nested_test)

    assert_equal(output_bytes, bytearray(
        [42, 2, 4, 6, 9, 8, 7, 14, 16, 18, 0xdb]))

    def assign_wrong_length_array():
        nested_test.matrix[1] = [9, 8, 7, 6]

    assert_raises(ValueError, assign_wrong_length_array)


def test_array_eq():
    first_test_struct = [("nums", b.array(3, b.uint8))]
    first_test_data = bytearray([2, 4, 6])

    second_test_struct = [("nums", b.array(4, b.uint8))]
    second_test_data = bytearray([2, 4, 6, 8])

    first_test_parsed = b.parse(first_test_data, first_test_struct)
    second_test_parsed = b.parse(second_test_data, second_test_struct)

    assert_equal(first_test_parsed, first_test_parsed)
    assert_not_equal(first_test_parsed, second_test_parsed)

    first_test_parsed_copy = b.parse(first_test_data, first_test_struct)
    assert_equal(first_test_parsed.nums, first_test_parsed_copy.nums)

    first_test_parsed_copy.nums[2] = 100

    assert_not_equal(first_test_parsed, first_test_parsed_copy)
    assert_not_equal(first_test_parsed.nums, first_test_parsed_copy.nums)


def test_printable_str():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])

    nested_test = b.parse(data, nested_array_struct)

    assert_equal(str(nested_test), """{
  first: 42
  matrix: [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
  last: 219
}""")


def test_nested_struct_str():
    data = bitstring.BitArray(bytearray(range(35)))

    supernested_test = b.parse(data, as_native_struct)

    expected = '\n'.join([
        '{',
        '  ubermatrix: [',
        '    {',
        '      first: 0',
        '      matrix: [[1, 2, 3], [4, 5, 6], [7, 8, 9]]',
        '      last: 10', '    }, ',
        '    {',
        '      first: 11',
        '      matrix: [[12, 13, 14], [15, 16, 17], [18, 19, 20]]',
        '      last: 21',
        '    }, ',
        '    {',
        '      first: 22',
        '      matrix: [[23, 24, 25], [26, 27, 28], [29, 30, 31]]',
        '      last: 32',
        '    }]',
        '  dummy: {',
        '      length: 33',
        '      ok: False',
        '    }',
        '}'])

    assert_equal(str(supernested_test), expected)


def test_conditional_str():
    true_data = bitstring.BitArray(bytearray([0b11001010, 0b11101000]))
    true_data.append('0b0')

    test_struct = b.parse(true_data, conditional_test)

    expected_lines = [
        "{",
        "  qux: True",
        "  frooz: 9",
        "  quxz: 93",
        "}"]

    assert_equal(str(test_struct), '\n'.join(expected_lines))


@raises(ValueError)
def test_write_non_obj():
    b.write("piiiineapples!")


def test_minimal_pylsdj_song():
    pulse_instrument = [
        ("envelope", b.byte),
    ]

    instrument = [
        ("instrument_type", b.enum(8, {
            0: 'pulse'
        })),
        (b.CONDITIONAL, "instrument_type", {
            "pulse": pulse_instrument
        })
    ]

    song = [
        ("instruments", b.array(1, instrument))
    ]

    DEFAULT_INSTRUMENT = bytearray([0, 0xa8])

    data_bytes = DEFAULT_INSTRUMENT

    parsed_song = b.parse(data_bytes, song)

    assert_equal(parsed_song.instruments[0].envelope, 0xa8)


def test_read_and_write_prefix():
    lsdsng_preamble = [
        ("name", b.string(8)),
        ("version", b.byte)
    ]

    data = 'hellomon'.encode('utf-8')

    data += bytearray([10, 20, 30, 40, 50])

    parsed = b.parse(data, lsdsng_preamble)

    assert_equal(len(parsed), 9 * 8)

    output_bytes = b.write(parsed)

    assert_equal(len(output_bytes), 9)


def test_get_slice():
    data = bytearray([0x61, 0x62, 0x63, 0x64, 0x65, 0x66])

    slice_test_format = [('arr', b.array(6, b.string(1)))]

    slice_test = b.parse(data, slice_test_format)

    assert_equal([b'a', b'b', b'c', b'd', b'e', b'f'], list(slice_test.arr))

    assert_equal([b'c', b'd', b'e', b'f'], slice_test.arr[2:])
    assert_equal([b'a', b'b'], slice_test.arr[:2])
    assert_equal([b'f', b'e', b'd', b'c', b'b', b'a'], slice_test.arr[::-1])
    assert_equal([b'c', b'd', b'e'], slice_test.arr[2:5])
    assert_equal([b'f', b'e', b'd'], slice_test.arr[5:2:-1])
    assert_equal([b'f', b'e', b'd'], slice_test.arr[:2:-1])


def test_new():
    format_spec = [("greeting", b.string(5)),
                   ("age", b.nibble)]

    empty_struct = b.new(format_spec)

    assert_equal(len(empty_struct), 8 * 5 + 4)

    assert_equal(empty_struct.greeting, b'\x00\x00\x00\x00\x00')
    assert_equal(empty_struct.age, 0)

    empty_struct.greeting = 'hello'
    empty_struct.age = 0xb

    output_bytes = b.write(empty_struct)
    assert_equal(output_bytes, bytearray([0x68, 0x65, 0x6c, 0x6c, 0x6f, 0xb0]))

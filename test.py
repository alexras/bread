#!/usr/bin/env python

import struct, sys, pprint, unittest, itertools, tempfile, os, json

import bread as b

# Shared structs for bread struct test

test_struct = [
    { "endianness" : b.BIG_ENDIAN },
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

nested_array_struct = [
    {"endianness" : b.BIG_ENDIAN},
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
    {"endianness" : b.BIG_ENDIAN},
    ("ubermatrix", b.array(3, nested_array_struct)),
    ("dummy", simple_struct)
]

def test_simple_struct():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    test = b.parse(data, spec = test_struct)

    assert test.__offsets__.flag_one == 0
    assert test.__offsets__.flag_two == 1
    assert test.__offsets__.flag_three == 2
    assert test.__offsets__.flag_four == 3
    assert test.__offsets__.first == 4
    assert test.__offsets__.blah == 16
    assert test.__offsets__.second == 32
    assert test.__offsets__.third == 96
    assert test.__offsets__.fourth == 160

    assert len(test) == 168

    assert test.flag_one == True
    assert test.flag_two == False
    assert test.flag_three == True
    assert test.flag_four == False
    assert test.first == 0xfb
    assert test.blah == 0xdddd

    assert test.second == -57
    assert test.third == 90
    assert test.fourth == 0

    output_data = b.write(test, test_struct)

    assert output_data == data

    expected_json_struct = {
        "flag_one" : True,
        "flag_two" : False,
        "flag_three" : True,
        "flag_four" : False,
        "first" : 0xfb,
        "blah" : 0xdddd,
        "second" : -57,
        "third" : 90,
        "fourth" : 0
    }

    assert json.loads(test.as_json()) == expected_json_struct

def test_updates_do_not_leak():
    data = struct.pack(">IqQb", 0xafb3dddd, -57, 90, 0)
    data2 = struct.pack(">IqQb", 0x1de0fafe, 24, 999999, 1)

    test = b.parse(data, test_struct)

    test2 = b.parse(data2, test_struct)

    # test2's offsets should be the same as test's

    assert test2.__offsets__.flag_one == 0
    assert test2.__offsets__.flag_two == 1
    assert test2.__offsets__.flag_three == 2
    assert test2.__offsets__.flag_four == 3
    assert test2.__offsets__.first == 4
    assert test2.__offsets__.blah == 16
    assert test2.__offsets__.second == 32
    assert test2.__offsets__.third == 96
    assert test2.__offsets__.fourth == 160

    assert len(test2) == 168

    assert test2.flag_one == False
    assert test2.flag_two == False
    assert test2.flag_three == False
    assert test2.flag_four == True
    assert test2.first == 0xde
    assert test2.blah == 0xfafe

    assert test2.second == 24
    assert test2.third == 999999
    assert test2.fourth == 1

    # Updating test2 shouldn't impact test

    assert test.flag_one == True
    assert test.flag_two == False
    assert test.flag_three == True
    assert test.flag_four == False
    assert test.first == 0xfb
    assert test.blah == 0xdddd

    assert test.second == -57
    assert test.third == 90
    assert test.fourth == 0


def test_array():
    data = bytearray([0b11111111, 0b10010101, 0b00010001])

    test_array_struct = [
        {"endianness" : b.BIG_ENDIAN},
        ("first", b.uint8),
        ("flags", b.array(8, b.boolean)),
        ("last", b.uint8)]

    array_test = b.parse(data, test_array_struct)

    assert array_test.__offsets__.first == 0
    assert array_test.__offsets__.flags == 8
    assert array_test.__offsets__.last == 16

    assert len(array_test) == 24

    assert (array_test.flags ==
            [True, False, False, True, False, True, False, True])

    assert b.write(array_test, test_array_struct) == data

def test_nested_array():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])

    nested_test = b.parse(data, nested_array_struct)

    assert nested_test.__offsets__.first == 0
    assert nested_test.__offsets__.matrix == 8
    assert nested_test.__offsets__.last == 80
    assert len(nested_test) == 88

    assert nested_test.first == 42

    for i in xrange(9):
        assert nested_test.matrix[i / 3][i % 3] == i

    assert nested_test.last == 0xdb

    assert b.write(nested_test, nested_array_struct) == data

    expected_json_struct = {
        "first" : 42,
        "matrix" : [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
        "last" : 0xdb
    }

    assert json.loads(nested_test.as_json()) == expected_json_struct

def test_nested_struct():
    data = bytearray(range(36))

    supernested_test = b.parse(data, deeply_nested_struct)

    assert supernested_test.__offsets__.ubermatrix == 0
    assert supernested_test.__offsets__.dummy == 264
    assert len(supernested_test) == 273

    assert len(supernested_test.ubermatrix) == 3

    current_byte = 0

    for substruct in supernested_test.ubermatrix:
        assert substruct.first == current_byte
        current_byte += 1

        for i, j in itertools.product(xrange(3), xrange(3)):
            assert substruct.matrix[i][j] == current_byte + i * 3 + j

        current_byte += 9

        assert substruct.last == current_byte
        current_byte += 1

    assert supernested_test.dummy.length == current_byte
    current_byte += 1
    assert supernested_test.dummy.ok == False

    assert (b.write(supernested_test, deeply_nested_struct) ==
            bytearray(range(34) + [0b0]))

    expected_json_struct = {
        "dummy" : {
            "length" : 33,
            "ok" : False
        },
        "ubermatrix" : [
            {
                "first" : 0,
                "matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                "last" : 10
            },
            {
                "first" : 11,
                "matrix": [[12, 13, 14], [15, 16, 17], [18, 19, 20]],
                "last" : 21
            },
            {
                "first" : 22,
                "matrix": [[23, 24, 25], [26, 27, 28], [29, 30, 31]],
                "last" : 32
            }
        ]
    }

    assert json.loads(supernested_test.as_json()) == expected_json_struct


def test_single_byte_fields():
    single_byte_fields_struct = [
        ("bit_0", b.bit),
        ("bit_1", b.bit),
        ("semi_nibble", b.semi_nibble),
        ("nibble", b.nibble)]

    data = bytearray([0b10110010])

    test = b.parse(data, single_byte_fields_struct)

    assert test.bit_0 == 1
    assert test.bit_1 == 0
    assert test.semi_nibble == 0b11
    assert test.nibble == 0b0010

    assert b.write(test, single_byte_fields_struct) == data

def test_endianness():
    endianness_test = [
        ("big_endian", b.uint32, {"endianness" : b.BIG_ENDIAN}),
        ("little_endian", b.uint32, {"endianness" : b.LITTLE_ENDIAN}),
        ("default_endian", b.uint32)]

    data = bytearray([0x01, 0x02, 0x03, 0x04] * 3)

    test = b.parse(data, endianness_test)

    assert test.big_endian == 0x01020304
    assert test.little_endian == 0x04030201
    assert test.default_endian == test.little_endian

    assert b.write(test, endianness_test) == data

def test_conditional():
    conditional_test = [
        ("qux", b.boolean),
        (b.CONDITIONAL, "qux", {
            False: [("fooz", b.byte), ("barz", b.byte)],
            True: [("frooz", b.nibble), ("quxz", b.byte)]
        })
    ]

    true_data = bytearray([0b11001010, 0b11101000])

    true_test = b.parse(true_data, conditional_test)

    assert true_test.qux == True
    assert hasattr(true_test, "frooz")
    assert not hasattr(true_test, "fooz")
    assert true_test.frooz == 0b1001
    assert true_test.quxz == 0b01011101

    assert b.write(true_test, conditional_test) == true_data

    false_data = bytearray([0b01001000, 0b10000000, 0b10000000])

    false_test = b.parse(false_data, conditional_test)
    assert false_test.qux == False
    assert hasattr(false_test, "fooz")
    assert not hasattr(false_test, "frooz")
    assert false_test.fooz == 0b10010001
    assert false_test.barz == 1

    assert b.write(false_test, conditional_test) == false_data

def test_str():
    str_test = [("msg", b.string(5))]

    data = bytearray([0x68, 0x65, 0x6c, 0x6c, 0x6f])
    result = b.parse(data, str_test)

    assert result.msg == "hello"

    assert b.write(result, str_test) == data

def test_enum():
    enum_test = [
        ("suit", b.enum(8, {
            0: "diamonds",
            1: "hearts",
            2: "spades",
            3: "clubs"
        }))]

    for value, suit in zip(range(4), ["diamonds", "hearts", "spades", "clubs"]):
        data = bytearray([value])
        result = b.parse(data, enum_test)

        assert result.suit == suit
        assert b.write(result, enum_test) == data

    try:
        data = bytearray([42])
        result = b.parse(data, enum_test)
        assert False, "Failed to throw an error"
    except ValueError, e:
        # expected
        pass

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

    assert result.suit == "joker"

    data = bytearray([2])
    result = b.parse(data, enum_test)

    assert result.suit == "spades"

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

    assert pulse.instrument_type == "pulse"
    assert pulse.pulse_foo == 19

    assert b.write(pulse, enum_test) == pulse_test

    wave_test = bytearray([1, 65])

    wave = b.parse(wave_test, enum_test)

    assert wave.instrument_type == "wave"
    assert wave.wave_foo == 65

    assert b.write(wave, enum_test) == wave_test

    kit_test = bytearray([2, 9])

    kit = b.parse(kit_test, enum_test)

    assert kit.instrument_type == "kit"
    assert kit.kit_foo == 9

    assert b.write(kit, enum_test) == kit_test

    noise_test = bytearray([3, 17])

    noise = b.parse(noise_test, enum_test)

    assert noise.instrument_type == "noise"
    assert noise.noise_foo == 17

    assert b.write(noise, enum_test) == noise_test

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

    assert result.unsigned_10b == 0b1101010111
    assert result.unsigned_14b == 0b10101000110101
    assert result.signed_20b == - 0b101010000101011101
    assert result.signed_4b == 0b0101

    assert b.write(result, intX_test) == in_bytes

def test_read_modify_write():
    data = bytearray(range(36))

    supernested_test = b.parse(data, deeply_nested_struct)

    assert supernested_test.ubermatrix[1].matrix[2][1] == 19

    supernested_test.ubermatrix[1].matrix[2][1] = 42

    written_data = b.write(supernested_test, deeply_nested_struct)

    re_read_data = b.parse(written_data, deeply_nested_struct)

    assert re_read_data.ubermatrix[1].matrix[2][1] == 42

def test_read_modify_write_with_offset():
    data = bytearray([4])

    parsed = b.parse(data, offset_struct)
    assert parsed.length == 5

    output = b.write(parsed, offset_struct)
    assert output == data

    parsed.length = 10

    output = b.write(parsed, offset_struct)

    assert output[0] == 9

def test_file_io():
    data = bytearray(range(36))

    supernested_test = b.parse(data, deeply_nested_struct)

    (handle, file_path) = tempfile.mkstemp()

    try:
        b.write(supernested_test, deeply_nested_struct, filename=file_path)

        with open(file_path, 'rb') as fp:
            supernested_test_from_file = b.parse(fp, deeply_nested_struct)

        for i,j,k in itertools.product(xrange(3), xrange(3), xrange(3)):
            assert (supernested_test_from_file.ubermatrix[i].matrix[j][k] ==
                    supernested_test.ubermatrix[i].matrix[j][k])
    finally:
        os.close(handle)
        os.unlink(file_path)

def test_comparison():
    data = struct.pack(">IqQb", 0xafb0dddd, -57, 90, 0)
    obj_1 = b.parse(data, spec = test_struct)
    obj_2 = b.parse(data, spec = test_struct)

    assert obj_1 == obj_2

    obj_2.flag_four = not obj_1.flag_four

    assert obj_1 != obj_2

    obj_2.flag_four = obj_1.flag_four

    assert obj_1 == obj_2

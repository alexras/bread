#!/usr/bin/env python

import bread, struct, sys, pprint, unittest, itertools

def test_basic_mask():
    assert bread.mask_bits(0xaf, 0, 3 == 0xa)

def test_shift_data():
    shift_data = [0x5d, 0xf0, 0x15] # 0b01011101, 0b11110000, 0b00010101
    assert bread.substring_bits(shift_data, 3, 3) == [0x1]
    assert bread.substring_bits(shift_data, 3, 13) == [0xef, 0x4]

# Shared structs for bread struct test

class TestStruct(bread.Struct):
    endianness = bread.big_endian

    flag_one = bread.Bool()
    flag_two = bread.Bool()
    flag_three = bread.Bool()
    flag_four = bread.Bool()
    first = bread.UInt8()
    pad_1 = bread.Padding(4)
    blah = bread.UInt16()

    second = bread.Int64()
    third = bread.UInt64()
    fourth = bread.Int8()

class NestedArrayStruct(bread.Struct):
    endianness = bread.big_endian

    first = bread.UInt8()
    matrix = bread.Array(3, bread.Array(3, bread.UInt8()))
    last = bread.UInt8()

class SimpleStruct(bread.Struct):
    length = bread.UInt8()
    ok = bread.Bool()

class DeeplyNestedStruct(bread.Struct):
    endianness = bread.big_endian

    ubermatrix = bread.Array(3, NestedArrayStruct())
    dummy = SimpleStruct()

def test_simple_struct():
    data = struct.pack(">IqQb", 0xafb3dddd, -57, 90, 0)

    test = TestStruct()

    assert test.OFFSETS.flag_one == 0
    assert test.OFFSETS.flag_two == 1
    assert test.OFFSETS.flag_three == 2
    assert test.OFFSETS.flag_four == 3
    assert test.OFFSETS.first == 4
    assert test.OFFSETS.pad_1 == 12
    assert test.OFFSETS.blah == 16
    assert test.OFFSETS.second == 32
    assert test.OFFSETS.third == 96
    assert test.OFFSETS.fourth == 160

    assert test.LENGTH == len(test) == 168

    test.load(data)

    assert test.flag_one == True
    assert test.flag_two == False
    assert test.flag_three == True
    assert test.flag_four == False
    assert test.first == 0xfb
    assert test.pad_1 == None
    assert test.blah == 0xdddd

    assert test.second == -57
    assert test.third == 90
    assert test.fourth == 0

def test_updates_do_not_leak():
    data = struct.pack(">IqQb", 0xafb3dddd, -57, 90, 0)
    data2 = struct.pack(">IqQb", 0x1de0fafe, 24, 999999, 1)

    test = TestStruct()
    test.load(data)

    test2 = TestStruct()

    # test2's offsets should be the same as test's

    assert test2.OFFSETS.flag_one == 0
    assert test2.OFFSETS.flag_two == 1
    assert test2.OFFSETS.flag_three == 2
    assert test2.OFFSETS.flag_four == 3
    assert test2.OFFSETS.first == 4
    assert test2.OFFSETS.pad_1 == 12
    assert test2.OFFSETS.blah == 16
    assert test2.OFFSETS.second == 32
    assert test2.OFFSETS.third == 96
    assert test2.OFFSETS.fourth == 160

    assert test2.LENGTH == 168

    test2.load(data2)

    assert test2.flag_one == False
    assert test2.flag_two == False
    assert test2.flag_three == False
    assert test2.flag_four == True
    assert test2.first == 0xde
    assert test2.pad_1 == None
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
    assert test.pad_1 == None
    assert test.blah == 0xdddd

    assert test.second == -57
    assert test.third == 90
    assert test.fourth == 0


def test_array():
    data = bytearray([0b11111111, 0b10010101, 0b00010001])

    class TestArrayStruct(bread.Struct):
        endianness = bread.big_endian

        first = bread.UInt8()
        flags = bread.Array(8, bread.Bool())
        last = bread.UInt8()

    array_test = TestArrayStruct()

    assert array_test.OFFSETS.first == 0
    assert array_test.OFFSETS.flags == 8
    assert array_test.OFFSETS.last == 16

    assert array_test.LENGTH == 24

    array_test.load(data)

    assert (array_test.flags ==
            [True, False, False, True, False, True, False, True])

def test_nested_array():
    data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])

    nested_test = NestedArrayStruct()

    assert nested_test.OFFSETS.first == 0
    assert nested_test.OFFSETS.matrix == 8
    assert nested_test.OFFSETS.last == 80
    assert nested_test.LENGTH == 88

    nested_test.load(data)

    assert nested_test.first == 42

    for i in xrange(9):
        assert nested_test.matrix[i / 3][i % 3] == i

    assert nested_test.last == 0xdb

def test_nested_struct():
    supernested_test = DeeplyNestedStruct()

    assert supernested_test.OFFSETS.ubermatrix == 0
    assert supernested_test.OFFSETS.dummy == 264
    assert supernested_test.LENGTH == 273
    assert len(supernested_test) == 273

    data = bytearray(range(36))

    supernested_test.load(data)

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

def test_bool_invalid_value():
    b = bread.Bool()

    try:
        b.load([5])
        assert False, "5 should not parse as a Bool"
    except ValueError, e:
        pass

def test_single_byte_fields():
    class SingleByteFieldsStruct(bread.Struct):
        bit_0 = bread.Bit()
        bit_1 = bread.Bit()
        semi_nibble = bread.SemiNibble()
        nibble = bread.Nibble()

    data = bytearray([0b10110010])

    test = SingleByteFieldsStruct()
    test.load(data)

    assert test.bit_0 == 1
    assert test.bit_1 == 0
    assert test.semi_nibble == 0b11
    assert test.nibble == 0b0010

def test_endianness():
    class EndianTestStruct(bread.Struct):
        big_endian = bread.UInt32(endianness = bread.big_endian)
        little_endian = bread.UInt32(endianness = bread.little_endian)
        default_endian = bread.UInt32()

    data = bytearray([0x01, 0x02, 0x03, 0x04] * 3)

    test = EndianTestStruct()

    test.load(data)

    assert test.big_endian == 0x01020304
    assert test.little_endian == 0x04030201
    assert test.default_endian == test.little_endian

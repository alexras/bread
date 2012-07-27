#!/usr/bin/env python

import bread
import struct
import sys

assert bread.mask_bits(0xaf, 0, 3) == 0xa

 # == [0b11101111, 0b100]
 # == [0xef, 0x4]

shift_data = [0x5d, 0xf0, 0x15] # 0b01011101, 0b11110000, 0b00010101
assert bread.substring_bits(shift_data, 3, 3) == [0x1]
assert bread.substring_bits(shift_data, 3, 13) == [0xef, 0x4]

data = struct.pack(">IqQb", 0xafb3dddd, -57, 90, 0)

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

test = TestStruct()

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

data2 = struct.pack(">IqQb", 0x1de0fafe, 24, 999999, 1)

test2 = TestStruct()

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

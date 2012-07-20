#!/usr/bin/env python

import bread
import struct

data = struct.pack(">IqQb", 32, -57, 90, 0)

class TestStruct(bread.Struct):
    endianness = bread.big_endian

    first = bread.UInt32()
    second = bread.Int64()
    third = bread.UInt64()
    fourth = bread.Int8()

test = TestStruct()

test.load(data)

assert test.first == 32
assert test.second == -57
assert test.third == 90
assert test.fourth == 0

data2 = struct.pack(">IqQb", 3, 24, 999999, 1)

test2 = TestStruct()

test2.load(data2)

assert test2.first == 3
assert test2.second == 24
assert test2.third == 999999
assert test2.fourth == 1

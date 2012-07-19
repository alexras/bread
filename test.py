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

print test.first
print test.second
print test.third
print test.fourth

data2 = struct.pack(">IqQb", 3, 24, 999999, 1)

test2 = TestStruct()

test2.load(data2)

print test2.first
print test2.second
print test2.third
print test2.fourth

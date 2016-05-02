# `bread` - Easier Binary Format Parsing

[![Build Status](https://travis-ci.org/alexras/bread.svg?branch=master)](https://travis-ci.org/alexras/bread) [![Coverage Status](https://coveralls.io/repos/alexras/bread/badge.svg?branch=master)](https://coveralls.io/r/alexras/bread?branch=master) [![Documentation Status](https://readthedocs.org/projects/bread/badge/?version=latest)](https://readthedocs.org/projects/bread/?badge=latest)


![](https://raw.github.com/alexras/bread/web/images/powdered-toast-man.jpg)

Reading binary formats is a pain. `bread` (short for "binary read", but
pronounced like the baked good) makes that simpler.

## Motivation

Here's an example from the documentation for Python's `struct` library:

```python
record = 'raymond   \x32\x12\x08\x01\x08'
name, serialnum, school, gradelevel = unpack('<10sHHb', record)
```

The format specification is dense, but it's also really hard to
understand. What was `H` again? is `b` signed? Am I sure I'm unpacking those
fields in the right order?

Now what happens if I have arrays of complex structures? Deeply nested
structures? This can get messy really fast.

## Leave Everything To Me!

`bread` understands a simple declarative specification of a binary format.

Here's the specification for the above example:

```python
import bread as b

record_spec = [
    {"endianness" : b.LITTLE_ENDIAN},
    ("name", b.string(10)),
    ("serialnum", b.uint16),
    ("school", b.uint16),
    ("gradelevel", b.byte)
]
```

Here's how to parse it:

```
parsed_record = b.parse(record, record_spec)

>>> parsed_record.name
"raymond   "

>>> parsed_record.school
264
```

Here's a more complicated example:

```python
nested_array_struct = [
    {"endianness" : b.BIG_ENDIAN},
    ("first", b.uint8),
    ("matrix", b.array(3, b.array(3, b.uint8))),
    ("last", b.uint8)
]

data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])
nested_parsed = b.parse(data, nested_array_struct)

>>> print nested_parsed
first: 42
matrix: [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
last: 219
```

## Installation

A recent stable version of `bread` can be installed by running

`$ pip install bread`

## Documentation

For the latest documentation, go to [https://bread.readthedocs.org/en/latest/](https://bread.readthedocs.org/en/latest/)

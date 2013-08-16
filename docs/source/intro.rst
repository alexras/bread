Introduction
============

In this section, we'll discuss why I wrote ``bread``, and give a rough sense of
what it can do.

Motivation
----------

Here's an example from the documentation for Python's ``struct`` library:::

    record = 'raymond   \x32\x12\x08\x01\x08'
    name, serialnum, school, gradelevel = unpack('<10sHHb', record)

The format specification is dense, but it's also really hard to
understand. What was ``H`` again? is ``b`` signed? Am I sure I'm unpacking those
fields in the right order?

Now what happens if I have arrays of complex structures? Deeply nested
structures? This can get messy really fast.

Here's ``bread``'s format specification for the above example:::

    import bread as b
    record_spec = [
        {"endianness" : b.LITTLE_ENDIAN},
        ("name", b.string(10)),
        ("serialnum", b.uint16),
        ("school", b.uint16),
        ("gradelevel", b.byte)
    ]

Here's how to parse using that specification:::

    >>> parsed_record = b.parse(record, record_spec)
    >>> parsed_record.name
    "raymond   "
    >>> parsed_record.school
    264

Here's a more complicated format specification:::

    nested_array_struct = [
        {"endianness" : b.BIG_ENDIAN},
        ("first", b.uint8),
        ("matrix", b.array(3, b.array(3, b.uint8))),
        ("last", b.uint8)
    ]

And how to parse using it:::

    >>> data = bytearray([42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 0xdb])
    >>> nested_parsed = b.parse(data, nested_array_struct)
    >>> print nested_parsed
    first: 42
    matrix: [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    last: 219

Goals (and Non-Goals)
---------------------

``bread`` was designed to read binary files into a read-only object format that
could be used by other tools. It's not really meant for writing binary data at
this point (although I can imagine future versions being able to do something
like that if I find the need).

I wrote ``bread`` with ease of use, rather than speed of execution, as a
first-order concern. That's not to say that ``bread`` is really slow, but if
you're writing something that analyzes gigabytes of binary data and speed is
your main concern, you may want to just roll your own optimized format reader
in something like C and call it a day.

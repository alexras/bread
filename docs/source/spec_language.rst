.. role:: py(code)
   :language: python
   :class: highlight

The Format Specification Language
=================================

``bread`` reads binary data according to a *format specification*. Format
specifications are just lists. Each element in the list is called a *field
descriptor*. Field descriptors describe how to consume a piece of binary data
from the input, usually to create a *field* in the resulting object. Field
descriptors are consumed from the format specification one at a time until the
entire list has been consumed.

Field Descriptors
-----------------

Most field descriptors will consume a certain amount of binary data and produce
a value of a certain basic type.

Integers
~~~~~~~~

``intX(num_bits, signed)`` - the next ``num_bits`` bits represent an integer. If
``signed`` is ``True``, the integer is interpreted as a signed, twos-complement
number.

For convenience and improved readability, the following shorthands are defined:

====================  ================  ==========
**Field Descriptor**  **Width (Bits)**  **Signed**
--------------------  ----------------  ----------
``bit``               1                 no
``semi_nibble``       2                 no
``nibble``            4                 no
``byte``              8                 no
``uint8``             8                 no
``uint16``            16                no
``uint32``            32                no
``uint64``            64                no
``int8``              8                 yes
``int16``             16                yes
``int32``             32                yes
``int64``             64                yes
====================  ================  ==========

Strings
~~~~~~~

``string(length)`` - the next ``length`` bytes represent a string of the given length

Booleans
~~~~~~~~

``boolean`` - the next bit represents a boolean value. 0 is ``False``, 1 is ``True``

Enumerations
~~~~~~~~~~~~

``enum(length, values, default=None)`` - the next ``length`` bits represent one
of a set of values, whose values are given by the dictionary ``values``. If
``default`` is specified, it will be returned if the bits do not correspond to
any value in ``values``. Otherwise, it raises a ``ValueError``.

Here is an example of a 2-bit field representing a card suit: ::

     import bread as b

     ("suit", b.enum(2, {
         0: "diamonds",
         1: "hearts",
         2: "spades",
         3: "clubs"
     }))

Arrays
~~~~~~

``array(count, field_or_struct)`` - the next piece of data is ``count``
occurrences of ``field_or_struct`` which, as the name might imply, can be
either a field (including another array) or a format specification.

Here's an example way of representing a deck of playing cards: ::

     import bread as b

     # A card is made up of a 2-bit suit and a 4-bit card number

     card = [
         ("suit", b.enum(2, {
             0: "diamonds",
             1: "hearts",
             2: "spades",
             3: "clubs"
         })),
         ("number", b.intX(4))]

     # A deck consists of 52 cards, for a total of 312 bits or 39 bytes of data

     deck = [("cards", b.array(52, card))]

Field Options
-------------

A dictionary of field options can be specified as the last argument to any
field. A dictionary of global field options can also be defined at the
beginning of the format spec (before any fields). Options defined on fields
override these global options.

The following field options are defined:

* ``str_format`` - the function that should be used to format a field in the
  structure's human-readable representation. For example: ::

       >>> import bread as b

       # Format spec without str_format ...
       >>> simple_spec = [('addr', b.uint8)]
       >>> parsed_data = b.parse(bytearray([42]), simple_spec)
       >>> print parsed_data
       addr: 42

       # ... and with str_format
       >>> simple_spec_hex = [('addr', b.uint8, {"str_format": hex})]
       >>> parsed_data = b.parse(bytearray([42]), simple_spec_hex)
       >>> print parsed_data
       addr: 0x2a

* ``endianness`` - for integer types, the endianness of the bytes that make up
  that integer. Can either be ``LITTLE_ENDIAN`` or ``BIG_ENDIAN``. Default is
  little-endian.

  A simple example: ::

       endianness_test = [
         ("big_endian", b.uint32, {"endianness" : b.BIG_ENDIAN}),
         ("little_endian", b.uint32, {"endianness" : b.LITTLE_ENDIAN}),
         ("default_endian", b.uint32)]

       data = bytearray([0x01, 0x02, 0x03, 0x04] * 3)
       test = b.parse(data, endianness_test)

       >>> test.big_endian == 0x01020304
       True
       >>> test.little_endian == 0x04030201
       True
       >>> test.default_endian == test.little_endian
       True

* ``offset`` - for integer types, the amount to add to the number after it has
  been parsed. Specifying a negative number will subtract that amount from the
  number.

Conditionals
------------

Conditionals allow the format specification to branch based on the value of a
previous field. Conditional field descriptors are specified as follows: ::

     (CONDITIONAL "field_name", options)

where ``field_name`` is the name of the field whose value determines the course
of the conditional, and ``options`` is a dictionary giving format
specifications to evaluate based on the field's value.

This is perhaps best illustrated by example: ::

     import bread as b

     # There are three kinds of widgets: type A, type B and type C. Each has
     # its own format spec.

     widget_A = [...]
     widget_B = [...]
     widget_C = [...]

     # A widget may be of any of the three types, determined by its type field

     widget = [
         ("type", b.string(1)),
         (b.CONDITIONAL, "type", {
             "A": widget_A,
             "B": widget_B,
             "C": widget_C
         })]

Padding
-------

``padding(num_bits)`` - indicates that the next ``num_bits`` bits should be
ignored. Useful in situations where only the first few bits of a byte are
meaningful, or where the format skips multiple bits or bytes.

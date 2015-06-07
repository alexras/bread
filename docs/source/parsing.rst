Parsing
-------

Currently, ``bread`` can parse data contained in strings, byte arrays, or
files. In all three cases, data parsing is done with the function ``parse(data, spec)``.

An example of parsing files: ::

      import bread as b

      format_spec = [...]

      with open('raw_file.bin', 'rb') as fp:
          parsed_obj = b.parse(fp, format_spec)


An example with byte arrays and strings: ::

     import bread as b

     format_spec = [("greeting", b.string(5))]

     bytes = bytearray([0x68, 0x65, 0x6c, 0x6c, 0x6f])
     string = "hello"

     parsed_bytes = b.parse(bytes, format_spec)
     parsed_string = b.parse(string, format_spec)

Parsed Object Methods
---------------------

Objects produced by bread can produce JSON representations of
themselves. Calling the object's ``as_json()`` method will produce its data as
a JSON string.

Objects produced by bread can also produce representations of themselves as
Pythonic ``list`` s, ``dict`` s, etc.  Calling the object's ``as_native()``
method will produce its data in this form.

Creating Empty Objects
----------------------

Sometimes, you want to write a binary format without having to read anything
first. To do this in Bread, you can use the function ``new(spec)``.

Here's an example of ``new()`` in action: ::

    format_spec = [("greeting", b.string(5)),
                   ("age", b.nibble)]

    empty_struct = b.new(format_spec)

    empty_struct.greeting = 'hello'
    empty_struct.age = 0xb

    output_bytes = b.write(empty_struct)

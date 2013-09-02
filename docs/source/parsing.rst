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

Writing
-------

*New in version 1.2*.

``write(parsed_obj, spec, filename=None)``

``bread`` allows you to parse data, modify it, and then write the modified
version back out again.

An example of reading, modifying and writing a file: ::

     import bread as b

     format_spec = [
         ('x', b.boolean),
         ('y', b.uint16)
     ]

     with open('raw_file.bin', 'rb') as fp:
         parsed_obj = b.parse(fp, format_spec)

     parsed_obj.y = 37

     # When called without a 'filename' argument, write() returns the raw
     # written data as a bytearray

     modified_data = write(parsed_obj, format_spec)

     # When called with a filename, write() writes the data to the named file
     write(parsed_obj, format_spec, filename='raw_file.bin.modified')

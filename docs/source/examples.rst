Examples
========

NSF Headers
-----------

The following parses the header for an `NES Sound Format (NSF) <http://kevtris.org/nes/nsfspec.txt>`_ file and prints it in a
human-readable format::

     import bread as b
     import sys

     def hex_array(x):
         return str(map(hex, x))

     nsf_header = [
         ('magic_number', b.array(5, b.byte),
          {"str_format": hex_array}),
         ('version', b.byte),
         ('total_songs', b.byte),
         ('starting_song', b.byte),
         ('load_addr', b.uint16, {"str_format": hex}),
         ('init_addr', b.uint16, {"str_format": hex}),
         ('play_addr', b.uint16, {"str_format": hex}),
         ('title', b.string(32)),
         ('artist', b.string(32)),
         ('copyright', b.string(32)),
         ('ntsc_speed', b.uint16),
         ('bankswitch_init', b.array(8, b.byte), {"str_format": hex_array}),
         ('pal_speed', b.uint16),
         ('ntsc', b.boolean),
         ('pal', b.boolean),
         ('ntsc_and_pal', b.boolean),
         (b.padding(6)),
         ('vrc6', b.boolean),
         ('vrc7', b.boolean),
         ('fds', b.boolean),
         ('mmc5', b.boolean),
         ('namco_106', b.boolean),
         ('fme07', b.boolean),
         (b.padding(2)),
         (b.padding(32))
     ]

     with open(sys.argv[1], 'r') as fp:
         header = b.parse(fp, nsf_header)
         print header

Here are a couple of examples of its output::

     $ python nsf_header.py Mega_Man_2.nsf

     magic_number: ['0x4e', '0x45', '0x53', '0x4d', '0x1a']
     version: 1
     total_songs: 24
     starting_song: 1
     load_addr: 0x8000
     init_addr: 0x8003
     play_addr: 0x8000
     title: Mega Man 2
     artist: Ogeretsu,Manami,Ietel,YuukiChan
     copyright: 1988,1989 Capcom Co. Ltd.
     ntsc_speed: 16666
     bankswitch_init: ['0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x0']
     pal_speed: 0
     ntsc: False
     pal: False
     ntsc_and_pal: False
     vrc6: False
     vrc7: False
     fds: False
     mmc5: False
     namco_106: False
     fme07: False

     $ python nsf_header.py Super_Mario_Bros.nsf

     magic_number: ['0x4e', '0x45', '0x53', '0x4d', '0x1a']
     version: 1
     total_songs: 18
     starting_song: 1
     load_addr: 0x8dc4
     init_addr: 0xbe34
     play_addr: 0xf2d0
     title: Super Mario Bros.
     artist: Koji Kondo
     copyright: 1985 Nintendo
     ntsc_speed: 16666
     bankswitch_init: ['0x0', '0x0', '0x0', '0x0', '0x1', '0x1', '0x1', '0x1']
     pal_speed: 0
     ntsc: False
     pal: False
     ntsc_and_pal: False
     vrc6: False
     vrc7: False
     fds: False
     mmc5: False
     namco_106: False
     fme07: False

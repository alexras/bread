class BreadField(object):
    def __init__(self, length, encode_fn, decode_fn, str_format):
        self._data_bits = None
        self.__offset = None
        self._length = length
        self._cached_value = None

        self._encode_fn = encode_fn
        self._decode_fn = decode_fn

        self._str_format = str_format

        self._name = None

    @property
    def _offset(self):
        return self.__offset

    @_offset.setter
    def _offset(self, value):
        self.__offset = value
        self._cached_value = None

    def _set_data(self, data_bits):
        self._data_bits = data_bits

    def __eq__(self, other):
        if not isinstance(other, BreadField):
            return False

        return self.get() == other.get()

    def __ne__(self, other):
        return not self.__eq__(other)

    def get(self):
        if self._cached_value is None:
            if self._offset is None:
                raise AttributeError(
                    "Haven't initialized the field '%s' with offsets yet" %
                    (self._name))

            start_bit = self._offset
            end_bit = self._offset + self._length

            value_bits = self._data_bits[start_bit:end_bit]
            self._cached_value = self._decode_fn(value_bits)

        return self._cached_value

    def as_native(self):
        return self.get()

    def __str__(self):
        return str(self.get())

    def set(self, value):
        value_bits = self._encode_fn(value)

        self._data_bits.overwrite(value_bits, self._offset)

        self._cached_value = value

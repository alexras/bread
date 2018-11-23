from .vendor.six.moves import range

from .struct import BreadConditional
from .constants import CONDITIONAL
from .struct import build_struct
from .utils import indent_text


class BreadArray(object):
    def __init__(self, num_items, parent, item_spec, field_options):
        self._num_items = num_items
        self.__offset = None
        self._name = None
        self.__item_length = None
        self._accessor_items = [None] * self._num_items
        self._item_spec = item_spec
        self._parent = parent
        self._data_bits = None
        self._field_options = field_options

    @property
    def _item_length(self):
        if self.__item_length is None:
            self.__item_length = self._get_accessor_item(0)._length

        return self.__item_length

    @property
    def _offset(self):
        return self.__offset

    @_offset.setter
    def _offset(self, offset):
        self.__offset = offset

        current_offset = offset

        for i in range(self._num_items):
            accessor = self._get_accessor_item(i)
            accessor._offset = current_offset

            current_offset += accessor._length


    def _create_accessor_item(self, index):
        if type(self._item_spec) == list:
            item = build_struct(self._item_spec)
        elif (type(self._item_spec) == tuple and
              self._item_spec[0] == CONDITIONAL):
            item = BreadConditional.from_spec(self._item_spec, self._parent)
        else:
            item = self._item_spec(self._parent, **(self._field_options))

        return item

    def _get_accessor_item(self, index):
        if self._accessor_items[index] is None:
            self._accessor_items[index] = self._create_accessor_item(index)

        return self._accessor_items[index]

    def __str__(self):
        string_repr = '['

        if self._num_items > 0:
            if type(self._item_spec) == list:
                str_function = lambda x: '\n' + indent_text(str(x))  # noqa: E731
            else:
                str_function = str

            item_strings = []

            for i in range(self._num_items):
                item_strings.append(str_function(self[i]))

            string_repr += ', '.join(item_strings)

        string_repr += ']'

        return string_repr

    @property
    def _length(self):
        return self._item_length * self._num_items

    def __getitem__(self, index):
        if type(index) is slice:
            start, stop, step = index.indices(self._num_items)

            return [self._get_accessor_item(i).get()
                    for i in range(start, stop, step)]
        else:
            if index < 0 or index >= self._num_items:
                raise IndexError('list index out of range')

            return self._get_accessor_item(index).get()

    def __setitem__(self, index, value):
        if index < 0 or index >= self._num_items:
            raise IndexError('list index out of range')

        self._get_accessor_item(index).set(value)

    def __len__(self):
        return self._num_items

    def __eq__(self, other):
        if isinstance(other, list):
            return [self[i] for i in range(self._num_items)] == other

        if not isinstance(other, BreadArray):
            return False

        if self._num_items != other._num_items:
            return False

        for i in range(self._num_items):
            if self[i] != other[i]:
                return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def get(self):
        return self

    def set(self, value):
        if type(value) != list:
            raise ValueError('Cannot set an array using a %s value' %
                             (str(type(value))))
        if len(value) != self._num_items:
            raise ValueError(
                'Cannot change the length of an array '
                '(would have changed from %d to %d)'
                % (self._num_items, len(value)))

        for i, item in enumerate(value):
            self._get_accessor_item(i).set(item)

    def as_native(self):
        native_items = []

        for i in range(self._num_items):
            native_items.append(self._get_accessor_item(i).as_native())

        return native_items

    def _set_data(self, data_bits):
        self._data_bits = data_bits

        for i in range(self._num_items):
            accessor = self._get_accessor_item(i)
            accessor._set_data(data_bits)


def array(length, substruct):
    def make_array_field(parent, **field_options):
        return BreadArray(length, parent, substruct, field_options)

    return make_array_field

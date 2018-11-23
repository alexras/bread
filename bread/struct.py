import json
import types

from bitstring import CreationError

from .constants import CONDITIONAL
from .errors import BadConditionalCaseError
from .utils import indent_text


class BreadStruct(object):
    def __init__(self):
        self._data_bits = None
        self._fields = {}
        self._conditional_fields = []
        self._field_list = []
        self._name = None

        # __offsets__ retained for backwards compatibility
        class Offsets(object):
            pass
        self.__offsets__ = Offsets()

    def __eq__(self, other):
        if not hasattr(other, '_data_bits'):
            return False

        return self._data_bits == other._data_bits

    def __ne__(self, other):
        return not self.__eq__(other)

    def __len__(self):
        return self._compute_length()

    def _get_min_length(self):
        total_length = 0

        for field in self._field_list:
            if isinstance(field, BreadConditional):
                total_length += field._get_min_length()
            else:
                total_length += field._length

        return total_length


    def _field_strings(self):
        field_strings = []

        for field in self._field_list:
            if isinstance(field, BreadStruct):
                field_strings.append(
                    field._name + ': ' + indent_text(str(field)).lstrip())
            elif isinstance(field, BreadConditional):
                field_strings.append(str(field))
            else:
                if field._name[0] != '_':
                    field_strings.append(field._name + ': ' + str(field))

        return field_strings

    def __str__(self):
        field_strings = self._field_strings()
        return '{\n' + '\n'.join(map(indent_text, field_strings)) + '\n}'

    def _set_data(self, data_bits):
        self._data_bits = data_bits

        for field in self._field_list:
            field._set_data(data_bits)

    @property
    def _offset(self):
        # A struct's offset is the offset where its first field starts
        return self._field_list[0]._offset

    @_offset.setter
    def _offset(self, value):
        offset = value

        # All fields offsets are relative to the starting offset for the struct
        for field in self._field_list:
            field._offset = offset
            offset += field._length

        for name, field in list(self._fields.items()):
            setattr(self.__offsets__, name, field._offset)

    def _compute_length(self):
        return sum([x._length for x in self._field_list])

    def get(self):
        return self

    def set(self, value):
        raise ValueError("Can't set a non-leaf struct to a value")

    def __getattr__(self, attr):
        if attr in ('_LENGTH', '_length'):
            return self._compute_length()

        if attr in self._fields:
            return self._fields[attr].get()

        for conditional_field in self._conditional_fields:
            try:
                return getattr(conditional_field, attr)
            except AttributeError:
                pass      # pragma: no cover

        raise AttributeError("No known field '%s'" % (attr))

    def __setattr__(self, attr, value):
        try:
            if attr[0] == '_':
                super(BreadStruct, self).__setattr__(attr, value)
            elif attr in self._fields:
                field = self._fields[attr]
                field.set(value)
            else:
                for conditional_field in self._conditional_fields:
                    try:
                        return setattr(conditional_field, attr, value)
                    except AttributeError:
                        pass

                raise AttributeError("No known field '%s'" % (attr))
        except CreationError as e:
            raise ValueError('Error while setting %s: %s' % (field._name, e))

    def _add_field(self, field, name):
        if name is not None:
            self._fields[name] = field
            field._name = name

        self._field_list.append(field)

        if isinstance(field, BreadConditional):
            self._conditional_fields.append(field)

    def as_native(self):
        native_struct = {}

        for field in self._field_list:
            if isinstance(field, BreadConditional):
                native_struct.update(field.as_native())
            elif field._name[0] != '_':
                native_struct[field._name] = field.as_native()
            elif isinstance(field, BreadConditional):
                native_struct.update(field.as_native())

        return native_struct

    def as_json(self):
        return json.dumps(self.as_native())


class BreadConditional(object):
    @staticmethod
    def from_spec(spec, parent):
        predicate_field_name, conditions = spec[1:]

        field = BreadConditional(predicate_field_name, parent)

        for predicate_value, condition in list(conditions.items()):
            condition_struct = build_struct(condition)
            field._add_condition(predicate_value, condition_struct)

        return field

    def __init__(self, conditional_field_name, parent_struct):
        self._name = None
        self._conditions = {}
        self._parent_struct = parent_struct
        self._conditional_field_name = conditional_field_name

    def _get_min_length(self):
        return min(map(lambda x: x._length, self._conditions.values()))

    def _set_data(self, data_bits):
        for struct in list(self._conditions.values()):
            struct._set_data(data_bits)

    def _add_condition(self, predicate_value, struct):
        self._conditions[predicate_value] = struct

    def _get_condition(self):
        switch_value = getattr(
            self._parent_struct, self._conditional_field_name)

        if switch_value not in self._conditions:
            raise BadConditionalCaseError(str(switch_value))

        return switch_value

    def __getattr__(self, attr):
        if attr == '_length':
            return self._conditions[self._get_condition()]._length

        if attr in ('_name', '_conditions', '_parent_struct'):
            return super(BreadConditional, self).__getattr__(attr)

        return getattr(self._conditions[self._get_condition()], attr)

    def __setattr__(self, attr, value):
        if attr[0] == '_':
            super(BreadConditional, self).__setattr__(attr, value)
        else:
            self._conditions[self._get_condition()].__setattr__(attr, value)


    def as_native(self):
        return self._conditions[self._get_condition()].as_native()

    def __str__(self):
        return '\n'.join(
            self._conditions[self._get_condition()]._field_strings())

    @property
    def _offset(self):
        return self._conditions[list(self._conditions.keys())[0]]._offset

    @_offset.setter
    def _offset(self, off):
        for condition_struct in list(self._conditions.values()):
            condition_struct._offset = off


def build_struct(spec, type_name=None):
    # Give different structs the appearance of having different type names
    class NewBreadStruct(BreadStruct):
        pass

    if type_name is not None:
        NewBreadStruct.__name__ = type_name

    struct = NewBreadStruct()

    global_options = {}

    unnamed_fields = 0

    for spec_line in spec:
        if type(spec_line) == dict:
            # A dictionary in the spec indicates global options for parsing
            global_options = spec_line
        elif isinstance(spec_line, types.FunctionType) or len(spec_line) == 1:
            # This part of the spec doesn't have a name; evaluate the function
            # to get the field object and then give that object a fake name.
            # Spec lines of length 1 are assumed to be functions.

            if isinstance(spec_line, types.FunctionType):
                field = spec_line
            else:
                field = spec_line[0]

            # Don't give the field a name
            struct._add_field(
                field(struct, **global_options), '_unnamed_%d' %
                (unnamed_fields))
            unnamed_fields += 1

        elif spec_line[0] == CONDITIONAL:
            predicate_field_name, conditions = spec_line[1:]

            field = BreadConditional.from_spec(spec_line, struct)

            struct._add_field(
                field, '_conditional_on_%s_%d' %
                (predicate_field_name, unnamed_fields))
            unnamed_fields += 1
        else:
            field_name = spec_line[0]
            field = spec_line[1]
            options = global_options

            # Options for this field, if any, override the global options
            if len(spec_line) == 3:
                options = global_options.copy()
                options.update(spec_line[2])

            if type(field) == list:
                struct._add_field(build_struct(field), field_name)
            else:
                struct._add_field(field(struct, **options), field_name)

    return struct

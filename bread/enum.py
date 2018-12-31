from .integer import intX


def _validate_key_types(enum_values):
    for key in enum_values.keys():
        if type(key) == int:
            continue

        valid = False

        if type(key) in (tuple, list):
            for alternative in key:
                valid = (type(alternative) == int)

        if not valid:
            raise ValueError("Keys in an enum's values dict should "
                             "be ints, int tuples, or int lists (%s)" % (enum_values))


def enum(length, values, default=None):
    def make_enum_field(parent, **field_options):
        enum_field = intX(length, signed=False)(parent, **field_options)

        old_encode_fn = enum_field._encode_fn
        old_decode_fn = enum_field._decode_fn

        keys = {}
        flattened_values = {}

        _validate_key_types(values)

        for k, v in values.items():
            if type(k) in (tuple, list):
                for alternative in k:
                    if type(alternative) is not int:
                        raise ValueError("Keys in an enum's values dict "
                                         "should be ints, tuples, or lists (%s)" % (values))

                    flattened_values[alternative] = v

                # If presented with a list of options for an enum's integer representation, always pick the first one
                keys[v] = k[0]
            elif type(k) == int:
                keys[v] = k
                flattened_values[k] = v
            else:
                raise ValueError("Keys in an enum's values dict should be ints, tuples, or lists (%s)" % (values))

        def encode_enum(key):
            if key not in keys:
                raise ValueError('%s is not a valid enum value; valid values %s' % (key, keys.keys()))

            return old_encode_fn(keys[key])

        def decode_enum(encoded):
            decoded_value = old_decode_fn(encoded)

            if decoded_value not in flattened_values:
                if default is not None:
                    return default
                else:
                    raise ValueError(
                        '%d is not a valid enum value; valid values %s' % (decoded_value, flattened_values))

            return flattened_values[decoded_value]

        enum_field._encode_fn = encode_enum
        enum_field._decode_fn = decode_enum

        return enum_field

    return make_enum_field

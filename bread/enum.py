from .integer import intX


def enum(length, values, default=None):
    def make_enum_field(parent, **field_options):
        enum_field = intX(length, signed=False)(parent, **field_options)

        old_encode_fn = enum_field._encode_fn
        old_decode_fn = enum_field._decode_fn

        keys = {v: k for k, v in list(values.items())}

        def encode_enum(key):
            if key not in keys:
                raise ValueError('%s is not a valid enum value; valid values %s' % (key, keys))

            return old_encode_fn(keys[key])

        def decode_enum(encoded):
            decoded_value = old_decode_fn(encoded)

            if decoded_value not in values:
                if default is not None:
                    return default
                else:
                    raise ValueError(
                        '%d is not a valid enum value; valid values %s' % (decoded_value, values))

            return values[decoded_value]

        enum_field._encode_fn = encode_enum
        enum_field._decode_fn = decode_enum

        return enum_field

    return make_enum_field

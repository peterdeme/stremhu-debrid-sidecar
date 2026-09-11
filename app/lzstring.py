"""compressToEncodedURIComponent from lz-string, just the compressor.

Debrid Media Manager builds its hash lists as an lz-string compressed JSON blob
in a URL fragment. Vendored rather than taken as a dependency: it is one pure
function, and tests/test_lzstring.py checks it byte-for-byte against the
reference implementation.

Port of https://github.com/pieroxy/lz-string (MIT).
"""

KEY_STR_URI_SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$"


def _compress(uncompressed, bits_per_char, get_char):
    if uncompressed is None:
        return ""

    context_dictionary = {}
    context_dictionary_to_create = {}
    context_c = ""  # noqa: F841  # unused here, kept to mirror the reference implementation
    context_wc = ""
    context_w = ""
    context_enlarge_in = 2
    context_dict_size = 3
    context_num_bits = 2
    context_data = []
    context_data_val = 0
    context_data_position = 0

    for c in uncompressed:
        if c not in context_dictionary:
            context_dictionary[c] = context_dict_size
            context_dict_size += 1
            context_dictionary_to_create[c] = True

        context_wc = context_w + c
        if context_wc in context_dictionary:
            context_w = context_wc
            continue

        if context_w in context_dictionary_to_create:
            if ord(context_w[0]) < 256:
                for _ in range(context_num_bits):
                    context_data_val = context_data_val << 1
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                value = ord(context_w[0])
                for _ in range(8):
                    context_data_val = (context_data_val << 1) | (value & 1)
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = value >> 1
            else:
                value = 1
                for _ in range(context_num_bits):
                    context_data_val = (context_data_val << 1) | value
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = 0
                value = ord(context_w[0])
                for _ in range(16):
                    context_data_val = (context_data_val << 1) | (value & 1)
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = value >> 1
            context_enlarge_in -= 1
            if context_enlarge_in == 0:
                context_enlarge_in = 2**context_num_bits
                context_num_bits += 1
            del context_dictionary_to_create[context_w]
        else:
            value = context_dictionary[context_w]
            for _ in range(context_num_bits):
                context_data_val = (context_data_val << 1) | (value & 1)
                if context_data_position == bits_per_char - 1:
                    context_data_position = 0
                    context_data.append(get_char(context_data_val))
                    context_data_val = 0
                else:
                    context_data_position += 1
                value = value >> 1

        context_enlarge_in -= 1
        if context_enlarge_in == 0:
            context_enlarge_in = 2**context_num_bits
            context_num_bits += 1

        context_dictionary[context_wc] = context_dict_size
        context_dict_size += 1
        context_w = c

    if context_w != "":
        if context_w in context_dictionary_to_create:
            if ord(context_w[0]) < 256:
                for _ in range(context_num_bits):
                    context_data_val = context_data_val << 1
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                value = ord(context_w[0])
                for _ in range(8):
                    context_data_val = (context_data_val << 1) | (value & 1)
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = value >> 1
            else:
                value = 1
                for _ in range(context_num_bits):
                    context_data_val = (context_data_val << 1) | value
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = 0
                value = ord(context_w[0])
                for _ in range(16):
                    context_data_val = (context_data_val << 1) | (value & 1)
                    if context_data_position == bits_per_char - 1:
                        context_data_position = 0
                        context_data.append(get_char(context_data_val))
                        context_data_val = 0
                    else:
                        context_data_position += 1
                    value = value >> 1
            context_enlarge_in -= 1
            if context_enlarge_in == 0:
                context_enlarge_in = 2**context_num_bits
                context_num_bits += 1
            del context_dictionary_to_create[context_w]
        else:
            value = context_dictionary[context_w]
            for _ in range(context_num_bits):
                context_data_val = (context_data_val << 1) | (value & 1)
                if context_data_position == bits_per_char - 1:
                    context_data_position = 0
                    context_data.append(get_char(context_data_val))
                    context_data_val = 0
                else:
                    context_data_position += 1
                value = value >> 1

        context_enlarge_in -= 1
        if context_enlarge_in == 0:
            context_enlarge_in = 2**context_num_bits
            context_num_bits += 1

    value = 2
    for _ in range(context_num_bits):
        context_data_val = (context_data_val << 1) | (value & 1)
        if context_data_position == bits_per_char - 1:
            context_data_position = 0
            context_data.append(get_char(context_data_val))
            context_data_val = 0
        else:
            context_data_position += 1
        value = value >> 1

    while True:
        context_data_val = context_data_val << 1
        if context_data_position == bits_per_char - 1:
            context_data.append(get_char(context_data_val))
            break
        context_data_position += 1

    return "".join(context_data)


def compress_to_encoded_uri_component(text):
    return _compress(text, 6, lambda i: KEY_STR_URI_SAFE[i])

def indent_text(string, indent_level=2):
    """Indent every line of text in a newline-delimited string"""
    indented_lines = []

    indent_spaces = ' ' * indent_level

    for line in string.split('\n'):
        indented_lines.append(indent_spaces + line)

    return '\n'.join(indented_lines)

"""Tiny helper for generating Pure Data patches from Python.

    p = Patch(w, h)
    a = p.obj('r foo', x, y)
    b = p.msg('bar $1', x, y)
    p.conn(a, b)            # outlet 0 -> inlet 0
    p.conn(a, b, 1, 0)
    p.save('file.pd')

Dollar signs and commas/semicolons are escaped for the Pd file format.
"""


def esc(text):
    return (text.replace('$', '\\$').replace(',', ' \\,').replace(';', ' \;')
            .replace('  ', ' '))


class Patch:
    def __init__(self, w=900, h=600, x=50, y=50):
        self.head = f'#N canvas {x} {y} {w} {h} 10;'
        self.lines, self.conns = [], []

    def _add(self, kind, text, x, y):
        self.lines.append(f'#X {kind} {x} {y} {esc(text)};' if text else f'#X {kind} {x} {y};')
        return len(self.lines) - 1

    def obj(self, text, x=0, y=0):
        return self._add('obj', text, x, y)

    def msg(self, text, x=0, y=0):
        return self._add('msg', text, x, y)

    def text(self, text, x=0, y=0):
        return self._add('text', text, x, y)

    def raw(self, line):
        """A pre-formatted '#X ...;' line (e.g. GUI objects) - no escaping."""
        self.lines.append(line)
        return len(self.lines) - 1

    def conn(self, a, b, outlet=0, inlet=0):
        self.conns.append(f'#X connect {a} {outlet} {b} {inlet};')

    def save(self, path):
        with open(path, 'w') as f:
            f.write('\n'.join([self.head] + self.lines + self.conns) + '\n')

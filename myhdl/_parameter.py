'''
Created on 20 jan. 2025

@author: josy
'''

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)


class Parameter(object):

    def __init__(self, val, package=False):
        '''
            val should either be:
              - a bool 
              - an integer, but restricted to 32 bits (signed)
              - an intbv, as wide as you want :)
        '''

        self._val = val
        self._package = package
        # not sure ifthis will be helpful
        self.parent = None
        # we accept the given `val` verbatim
        if isinstance(val, Parameter):
            self.parent = val
            self._val = val._val
        # make it look a bit like a _Signal
        self._type = type(val)
        self._name = None
        self._driven = None
        self._driver = None
        self._read = False
        self._readers = []
        self._used = False

        # ic(self._val)

    def _clear(self):
        # no action, of course!
        pass

    # 'used' attribute
    def _markUsed(self):
        self._used = True

    # # method lookup delegation
    # def __getattr__(self, attr):
    #     return getattr(self._val, attr)

    @property
    def _info(self):
        return f'{id(self)} {repr(self)} used {self._used}, driven {self._driven}, driver {self._driver}, read {self._read}, readers {self._readers} '

    # representation
    def __str__(self):
        if self._name:
            return self._name
        else:
            return str(self._val)

    def __repr__(self):
        if self._name:
            return f"{self._name} = Parameter({repr(self._val)}, package={self._package})"
        else:
            return f"Parameter({repr(self._val)}, package={self._package})"

    @property
    def value(self):
        return self._val

    def toSystemVerilog(self):
        # ic(self)
        if hasattr(self._val, '_toSystemVerilog'):
            return self._val._toSystemVerilog()
        else:
            return f'{self._val}'

    # how to defer ...? to the _type
    # maybe complicated
    # so we just type them all :(

    def __getitem__(self, key):
        return self._val[key]

    def __add__(self, other):
        return self._val.__add__(other)

    def __radd__(self, other):
        return self._val.__radd__(other)

    def __sub__(self, other):
        return self._val.__sub__(other)

    def __rsub__(self, other):
        return self._val.__rsub__(other)

    def __mul____(self, other):
        return self._mul.__mul__(other)

    def __rmul____(self, other):
        return self._val.__rmul__(other)

    def __truediv____(self, other):
        return self._mul.__truediv__(other)

    def __rtruediv____(self, other):
        return self._val.__rtruediv__(other)

    def __floordiv____(self, other):
        return self._mul.__floordiv__(other)

    def __rfloordiv____(self, other):
        return self._val.__rfloordiv__(other)

    def __mod__(self, other):
        return self._val.__mod__(self, other)

    def __rmod__(self, other):
        return self._val.__rmod__(self, other)

    def __pow__(self, other):
        return self._val.__pow__(self, other)

    def __rpow__(self, other):
        return self._val.__rpow__(self, other)

    def __lsfhift(self, other):
        return self._val.__lsfhift(self, other)

    def __rlsfhift(self, other):
        return self._val.__rlsfhift(self, other)

    def __rsfhift(self, other):
        return self._val.__rsfhift(self, other)

    def __rrsfhift(self, other):
        return self._val.__rrsfhift(self, other)

    # we don't have the __ixxx__() methods as parameters
    # are constant by nature

    def __int__(self):
        return int(self._val)

    def __long__(self):
        return int(self._val)

    def __float__(self):
        return float(self._val)

    def __oct__(self):
        return oct(self._val)

    def __hex__(self):
        return hex(self._val)

    def __index__(self):
        return int(self._val)

    def __neg__(self):
        return self._val.__neg__(self)

    def __pos__(self):
        return self._val.__pos__(self)

    def __abs__(self):
        return self._val.__abs__(self)

    def __invert__(self):
        return self._val.__invert__(self)

    def __eq__(self, other):
        return self._val.__eq__(other)

    def __ne__(self, other):
        return self._val.__ne__(other)

    def __lt__(self, other):
        return self._val.__lt__(other)

    def __le__(self, other):
        return self._val.__le__(other)

    def __gt__(self, other):
        return self._val.__gt__(other)

    def __ge__(self, other):
        return self._val.__ge__(other)


if __name__ == '__main__':
    pass

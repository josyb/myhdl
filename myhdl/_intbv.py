#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2015 Jan Decaluwe
#
#  The myhdl library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public License as
#  published by the Free Software Foundation; either version 2.1 of the
#  License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.

#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

""" Module with the intbv class """
import builtins

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl._bin import bin


class intbv(object):
    # __slots__ = ('_val', '_min', '_max', '_nrbits', '_handleBounds')

    def __init__(self, val=0, min=None, max=None, _nrbits=0):
        if _nrbits:
            self._min = 0
            self._max = 2 ** _nrbits
        else:
            self._min = min
            self._max = max
            if max is not None and min is not None:
                if min >= 0:
                    _nrbits = len(bin(max - 1))
                elif max <= 1:
                    _nrbits = len(bin(min))
                else:
                    # make sure there is a leading zero bit in positive numbers
                    _nrbits = builtins.max(len(bin(max - 1)) + 1, len(bin(min)))

        if isinstance(val, int):
            self._val = val
        elif isinstance(val, str):
            mval = val.replace('_', '')
            self._val = int(mval, 2)
            _nrbits = len(mval)
        elif isinstance(val, intbv):
            self._val = val._val
            self._min = val._min
            self._max = val._max
            _nrbits = val._nrbits
        else:
            raise TypeError(f"intbv constructor arg {repr(val)} should be int, intbv or string")
        self._nrbits = _nrbits
        self._handleBounds()

    # support for the 'min' and 'max' attribute
    @property
    def max(self):
        return self._max

    @property
    def min(self):
        return self._min

    def _handleBounds(self):
        if self._max is not None:
            if self._val >= self._max:
                raise ValueError(f"intbv value {self._val} >= maximum {self._max}")
        if self._min is not None:
            if self._val < self._min:
                raise ValueError(f"intbv value {self._val} < minimum {self._min}")

    def _hasFullRange(self):
        _min, _max = self._min, self._max
        if _max <= 0:
            return False
        if _min not in (0, -_max):
            return False
        return _max & _max - 1 == 0

    @property
    def issigned(self):
        return True if self._min is not None and self._min < 0 else False

    # hash
    def __hash__(self):
        raise TypeError(f"{self.__class__} objects are unhashable")

    # copy methods
    def __copy__(self):
        c = type(self)(self._val)
        c._min = self._min
        c._max = self._max
        c._nrbits = self._nrbits
        return c

    def __deepcopy__(self, visit):
        c = type(self)(self._val)
        c._min = self._min
        c._max = self._max
        c._nrbits = self._nrbits
        return c

    # iterator method
    def __iter__(self):
        if not self._nrbits:
            raise TypeError(f"Cannot iterate over unconstrained {self.__class__}")
        return iter([self[i] for i in range(self._nrbits - 1, -1, -1)])

    # logical testing
    def __bool__(self):
        return bool(self._val)

    __nonzero__ = __bool__

    # length
    def __len__(self):
        return self._nrbits

    # indexing and slicing methods

    def __getitem__(self, key):
        if isinstance(key, slice):
            i, j = key.start, key.stop
            if j is None:  # default
                j = 0
            j = int(j)
            if j < 0:
                raise ValueError("intbv[i:j] requires j >= 0\n"
                                 f"            j == {j}")
            if i is None:  # default
                return intbv(self._val >> j)
            i = int(i)
            if i <= j:
                raise ValueError("intbv[i:j] requires i > j\n"
                                 f"            i, j == {i}, {j}")
            res = intbv((self._val & (1 << i) - 1) >> j, _nrbits=i - j)
            return res
            # upper, lower = key.start, key.stop
            # if self._nrbits:
            #     if lower is None:
            #         lower = 0
            #     else:
            #         lower = int(lower)
            #         if lower < 0:
            #             lower = self._nrbits + lower
            #         if lower < 0:
            #             raise ValueError(f'lower: {key.stop} results in negative stop index {lower}')
            #     if upper is None:
            #         upper = self._nrbits - 1
            #     else:
            #         upper = int(upper)
            #         if upper < 0:
            #             upper = self._nrbits + upper
            #         if upper < 0:
            #             raise ValueError(f'upper: {key.start} results in negative start index {upper}')
            #     return intbv((self._val & ((1 << upper) - 1)) >> lower, _nrbits=upper - lower)
            # else:
            #     # unconstrained
            #     if upper is  None and lower is None:
            #         raise ValueError(f'Cannot slice unconstrained intbv[{upper}:{lower}]')
            #     if lower is None:
            #         lower = 0
            #     else:
            #         lower = int(lower)
            #         if lower < 0:
            #             raise ValueError(f'Slicing unconstrained intbv cannot accept negative lower {lower}')
            #     if upper is None:
            #         return intbv(self._val >> lower)
            #     else:
            #         upper = int(upper)
            #         if upper < 0:
            #             raise ValueError(f'Slicing unconstrained intbv cannot accept negative upper {upper}')
            #         return intbv(self._val & ((1 << upper) - 1) >> lower, _nrbits=upper - lower)

        else:
            i = int(key)
            res = bool((self._val >> i) & 0x1)
            return res

    def __setitem__(self, key, val):
        # convert val to int to avoid confusion with intbv or Signals
        val = int(val)
        if isinstance(key, slice):
            i, j = key.start, key.stop
            if j is None:  # default
                j = 0
            j = int(j)
            if j < 0:
                raise ValueError("intbv[i:j] = v requires j >= 0\n"
                                 f"            j == {j}")
            if i is None:  # default
                q = self._val % (1 << j)
                self._val = val * (1 << j) + q
                self._handleBounds()
                return
            i = int(i)
            if i <= j:
                raise ValueError("intbv[i:j] = v requires i > j\n"
                                 f"            i, j, v =={i}, {j}, {val}")
            lim = (1 << (i - j))
            if val >= lim or val < -lim:
                raise ValueError("intbv[i:j] = v abs(v) too large\n"
                                 f"            i, j, v =={i}, {j}, {val}")
            mask = (lim - 1) << j
            self._val &= ~mask
            self._val |= (val << j)
            self._handleBounds()
        else:
            i = int(key)
            if val == 1:
                self._val |= (1 << i)
            elif val == 0:
                self._val &= ~(1 << i)
            else:
                raise ValueError("intbv[i] = v requires v in (0, 1)\n"
                                 f"            i == {i}")

            self._handleBounds()

    # integer-like methods

    def __add__(self, other):
        if isinstance(other, intbv):
            return self._val + other._val
        else:
            return self._val + other

    def __radd__(self, other):
        return other + self._val

    def __sub__(self, other):
        if isinstance(other, intbv):
            return self._val - other._val
        else:
            return self._val - other

    def __rsub__(self, other):
        return other - self._val

    def __mul__(self, other):
        if isinstance(other, intbv):
            return self._val * other._val
        else:
            return self._val * other

    def __rmul__(self, other):
        return other * self._val

    def __truediv__(self, other):
        if isinstance(other, intbv):
            return self._val / other._val
        else:
            return self._val / other

    def __rtruediv__(self, other):
        return other / self._val

    def __floordiv__(self, other):
        if isinstance(other, intbv):
            return self._val // other._val
        else:
            return self._val // other

    def __rfloordiv__(self, other):
        return other // self._val

    def __mod__(self, other):
        if isinstance(other, intbv):
            return self._val % other._val
        else:
            return self._val % other

    def __rmod__(self, other):
        return other % self._val

    # divmod

    def __pow__(self, other):
        if isinstance(other, intbv):
            return self._val ** other._val
        else:
            return self._val ** other

    def __rpow__(self, other):
        return other ** self._val

    def __lshift__(self, other):
        if isinstance(other, intbv):
            return intbv(int(self._val) << other._val)
        else:
            return intbv(int(self._val) << other)

    def __rlshift__(self, other):
        return other << self._val

    def __rshift__(self, other):
        if isinstance(other, intbv):
            return intbv(self._val >> other._val)
        else:
            return intbv(self._val >> other)

    def __rrshift__(self, other):
        return other >> self._val

    def __and__(self, other):
        if isinstance(other, intbv):
            return intbv(self._val & other._val)
        else:
            return intbv(self._val & other)

    def __rand__(self, other):
        return intbv(other & self._val)

    def __or__(self, other):
        if isinstance(other, intbv):
            return intbv(self._val | other._val)
        else:
            return intbv(self._val | other)

    def __ror__(self, other):
        return intbv(other | self._val)

    def __xor__(self, other):
        if isinstance(other, intbv):
            return intbv(self._val ^ other._val)
        else:
            return intbv(self._val ^ other)

    def __rxor__(self, other):
        return intbv(other ^ self._val)

    def __iadd__(self, other):
        if isinstance(other, intbv):
            self._val += other._val
        else:
            self._val += other
        self._handleBounds()
        return self

    def __isub__(self, other):
        if isinstance(other, intbv):
            self._val -= other._val
        else:
            self._val -= other
        self._handleBounds()
        return self

    def __imul__(self, other):
        if isinstance(other, intbv):
            self._val *= other._val
        else:
            self._val *= other
        self._handleBounds()
        return self

    def __ifloordiv__(self, other):
        if isinstance(other, intbv):
            self._val //= other._val
        else:
            self._val //= other
        self._handleBounds()
        return self

    def __idiv__(self, other):
        raise TypeError("intbv: Augmented classic division not supported")

    def __itruediv__(self, other):
        raise TypeError("intbv: Augmented true division not supported")

    def __imod__(self, other):
        if isinstance(other, intbv):
            self._val %= other._val
        else:
            self._val %= other
        self._handleBounds()
        return self

    def __ipow__(self, other, modulo=None):
        # XXX why 3rd param required?
        # unused but needed in 2.2, not in 2.3
        if isinstance(other, intbv):
            self._val **= other._val
        else:
            self._val **= other
        if not isinstance(self._val, int):
            raise ValueError(f"intbv value should be integer (<> {self._val}")
        self._handleBounds()
        return self

    def __iand__(self, other):
        if isinstance(other, intbv):
            self._val &= other._val
        else:
            self._val &= other
        self._handleBounds()
        return self

    def __ior__(self, other):
        if isinstance(other, intbv):
            self._val |= other._val
        else:
            self._val |= other
        self._handleBounds()
        return self

    def __ixor__(self, other):
        if isinstance(other, intbv):
            self._val ^= other._val
        else:
            self._val ^= other
        self._handleBounds()
        return self

    def __ilshift__(self, other):
        self._val = int(self._val)
        if isinstance(other, intbv):
            self._val <<= other._val
        else:
            self._val <<= other
        self._handleBounds()
        return self

    def __irshift__(self, other):
        if isinstance(other, intbv):
            self._val >>= other._val
        else:
            self._val >>= other
        self._handleBounds()
        return self

    def __neg__(self):
        return -self._val

    def __pos__(self):
        return self._val

    def __abs__(self):
        return abs(self._val)

    def __invert__(self):
        if self._nrbits and self._min >= 0:
            return intbv(~self._val & (1 << self._nrbits) - 1)
        else:
            return intbv(~self._val)

    def __int__(self):
        return int(self._val)

    def __long__(self):
        return int(self._val)

    def __float__(self):
        return float(self._val)

    # XXX __complex__ seems redundant ??? (complex() works as such?)

    def __oct__(self):
        return oct(self._val)

    def __hex__(self):
        return hex(self._val)

    def __index__(self):
        return int(self._val)

    # comparisons
    def __eq__(self, other):
        # ic(self, other)
        if isinstance(other, intbv):
            return self._val == other._val
        else:
            return self._val == other

    def __ne__(self, other):
        if isinstance(other, intbv):
            return self._val != other._val
        else:
            return self._val != other

    def __lt__(self, other):
        if isinstance(other, intbv):
            return self._val < other._val
        else:
            return self._val < other

    def __le__(self, other):
        if isinstance(other, intbv):
            return self._val <= other._val
        else:
            return self._val <= other

    def __gt__(self, other):
        if isinstance(other, intbv):
            return self._val > other._val
        else:
            return self._val > other

    def __ge__(self, other):
        if isinstance(other, intbv):
            return self._val >= other._val
        else:
            return self._val >= other

    # representation
    def __str__(self):
        # represent in hex format, to handle VHDL long vectors
        v = int(self._val)
        nrbits = self._nrbits
        if nrbits:
            # represent negative values without minus sign
            # I would prefer sign extension with hex format, but to
            # align with Verilog $display I don't do that
            if v < 0:
                v = 2 ** nrbits + v
            w = (nrbits - 1) // 4 + 1
            return f"{v:0{w}x}"
        else:
            return f"{v:x}"

    def __repr__(self):
        nrbits = self._nrbits
        if nrbits:
            # return "intbv(" + repr(self._val) + ")[{}:]".format(self._nrbits)
            return f"intbv({repr(self._val)})[{self._nrbits}:]"
        else:
            return f"intbv({repr(self._val)})"

    def __format__(self, specification):
        if specification == 'x':
            ndigits = (self._nrbits + 3) // 4
            # print(specification, ndigits)
            # return '{:0{}x}'.format(self._val, ndigits,)
            return f'{self._val:0{ndigits}x}'
        else:
            return f'{self._val}'

    def signed(self):
        ''' Return new intbv with the values interpreted as signed

        The intbv.signed() function will classify the value of the intbv
        instance either as signed or unsigned. If the value is classified
        as signed it will be returned unchanged as integer value. If the
        value is considered unsigned, the bits as specified by _nrbits
        will be considered as 2's complement number and returned. This
        feature will allow to create slices and have the sliced bits be
        considered a 2's complement number.

        The classification is based on the following possible combinations
        of the min and max value.

        ----+----+----+----+----+----+----+----
           -3   -2   -1    0    1    2    3
        1                   min  max
        2                        min  max
        3              min       max
        4              min            max
        5         min            max
        6         min       max
        7         min  max
        8   neither min nor max is set
        9   only max is set
        10  only min is set

        From the above cases, # 1 and 2 are considered unsigned and the
        signed() function will convert the value to a signed number.
        Decision about the sign will be done based on the msb. The msb is
        based on the _nrbits value.

        So the test will be if min >= 0 and _nrbits > 0. Then the instance
        is considered unsigned and the value is returned as 2's complement
        number.
        '''

        # value is considered unsigned
        if self.min is not None and self.min >= 0 and self._nrbits:

            # get 2's complement value of bits
            msb = self._nrbits - 1

            sign = ((self._val >> msb) & 0x1) > 0

            # mask off the bits msb-1:lsb, they are always positive
            mask = (1 << msb) - 1
            retVal = self._val & mask
            # if sign bit is set, subtract the value of the sign bit
            if sign:
                retVal -= 1 << msb

        else:  # value is returned just as is
            retVal = self._val

        if self._nrbits:
            M = 2 ** (self._nrbits - 1)
            return intbv(retVal, min=-M, max=M)
        else:
            return intbv(retVal)

    def unsigned(self):
        ''' Return new intbv with the values interpreted as unsigned
        '''

        # value is considered unsigned
        if self.min is not None and self.min < 0 and self._nrbits:
            mask = (1 << self._nrbits) - 1
            retVal = self._val & mask

        else:  # value is returned just as is
            retVal = self._val

        if self._nrbits:
            return intbv(retVal)[self._nrbits:]
        else:
            return intbv(retVal)

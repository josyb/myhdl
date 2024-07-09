#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2024 Jan Decaluwe
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

'''
Created on 31 mrt. 2024

@author: josy

Module to replace usage of bool() by a dedicated object: bit()
'''


class bit(object):
    '''
        We have chosen *not* to subclass bit() from int()
        it may be more typing work now
        but it will be clear how it works
        Python's BDFL did subclass bool() form int(), and he himself said that itis flawed; 
        see https://github.com/python/cpython/pull/103487#issuecomment-1950294605
    '''
    slots = ('_val', '_nrbits')

    def __init__(self, val=0):
        ''' val can be any object '''
        self._val = 1 if bool(val) else 0
        self._nrbits = 1

    # hash
    def __hash__(self):
        raise TypeError("bit objects are unhashable")

    # copy methods
    def __copy__(self):
        c = type(self)(self._val)
        return c

    def __deepcopy__(self, visit):
        c = type(self)(self._val)
        return c

    # logical testing
    def __bool__(self):
        return bool(self._val)

    # length
    def __len__(self):
        return 1

    def __and__(self, other):
        if isinstance(other, bit):
            return bit(self._val & other._val)
        else:
            return bit(self._val & other)

    def __rand__(self, other):
        return bit(other & self._val)

    def __or__(self, other):
        if isinstance(other, bit):
            return bit(self._val | other._val)
        else:
            return bit(self._val | other)

    def __ror__(self, other):
        return bit(other | self._val)

    def __xor__(self, other):
        if isinstance(other, bit):
            return bit(self._val ^ other._val)
        else:
            return bit(self._val ^ other)

    def __rxor__(self, other):
        return bit(other ^ self._val)

    def __iand__(self, other):
        if isinstance(other, bit):
            self._val &= other._val
        else:
            self._val &= 1 if other else 0
        return self

    def __ior__(self, other):
        if isinstance(other, bit):
            self._val |= other._val
        else:
            self._val |= 1 if other else 0
        return self

    def __ixor__(self, other):
        if isinstance(other, bit):
            self._val ^= other._val
        else:
            self._val ^= 1 if other else 0
        return self

    def __neg__(self):
        return -self._val

    def __pos__(self):
        return self._val

    def __abs__(self):
        return abs(self._val)

    def __invert__(self):
        return bit(0 if self._val else 1)

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

    # comparisons
    def __eq__(self, other):
        if isinstance(other, bit):
            return self._val == other._val
        else:
            return self._val == other

    def __ne__(self, other):
        if isinstance(other, bit):
            return self._val != other._val
        else:
            return self._val != other

    def __lt__(self, other):
        if isinstance(other, bit):
            return self._val < other._val
        else:
            return self._val < other

    def __le__(self, other):
        if isinstance(other, bit):
            return self._val <= other._val
        else:
            return self._val <= other

    def __gt__(self, other):
        if isinstance(other, bit):
            return self._val > other._val
        else:
            return self._val > other

    def __ge__(self, other):
        if isinstance(other, bit):
            return self._val >= other._val
        else:
            return self._val >= other

    # representation
    def __str__(self):
        return f'{self._val}'

    def __repr__(self):
        return f'bit({self._val})'


if __name__ == '__main__':
    pass

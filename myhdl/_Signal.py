#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2011 Jan Decaluwe
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

""" Module that provides the Signal class and related objects.

This module provides the following objects:

Signal -- class to model hardware signals
posedge -- callable to model a rising edge on a signal in a yield statement
negedge -- callable to model a falling edge on a signal in a yield statement

"""
from copy import copy, deepcopy

from myhdl import _simulator as sim
from myhdl._simulator import _futureEvents
from myhdl._simulator import _siglist
from myhdl._simulator import _signals
from myhdl._intbv import intbv
from myhdl._bit import bit
from myhdl._bin import bin

# from myhdl._enum import EnumItemType

_schedule = _futureEvents.append


def _isListOfSigs(obj):
    """ Check if obj is a non-empty list of signals. """
    if isinstance(obj, list) and len(obj) > 0:
        for e in obj:
            if not isinstance(e, _Signal):
                return False
        return True
    else:
        return False


class _WaiterList(list):

    def purge(self):
        if self:
            self[:] = [w for w in self if not w.hasRun]


class _PosedgeWaiterList(_WaiterList):

    def __init__(self, sig):
        self.sig = sig

    def _toVerilog(self):
        return f"posedge {self.sig._name}"

    def _toVHDL(self):
        return f"rising_edge({self.sig._name})"

    def __repr__(self):
        return f'_PosedgeWaiterList({self.sig._name})'


class _NegedgeWaiterList(_WaiterList):

    def __init__(self, sig):
        self.sig = sig

    def _toVerilog(self):
        return f"negedge {self.sig._name}"

    def _toVHDL(self):
        return f"falling_edge({self.sig._name})"

    def __repr__(self):
        return f'_NegedgeWaiterList({self.sig._name})'


def posedge(sig):
    """ Return a posedge trigger object """
    return sig.posedge


def negedge(sig):
    """ Return a negedge trigger object """
    return sig.negedge

# signal factory function


def Signal(val=None, delay=None):
    """ Return a new _Signal (default or delay 0) or DelayedSignal """
    if delay is not None:
        if delay < 0:
            raise TypeError(f"Signal: delay should be >= 0")
        return _DelayedSignal(val, delay)
    else:
        return _Signal(val)


class _Signal(object):

    """ _Signal class.

    Properties:
    val -- current value (read-only)
    next -- next value (read-write)

    """

    __slots__ = ('_next', '_val', '_min', '_max', '_type', '_init',
                 '_eventWaiters', '_posedgeWaiters', '_negedgeWaiters',
                 '_code', '_tracing', '_nrbits', '_checkVal',
                 '_setNextVal', '_copyVal2Next', '_printVcd',
                 '_driven', '_read', '_name', '_used', '_inList',
                 '_waiter', 'toVHDL', 'toVerilog', '_slicesigs',
                 '_numeric'
                 )

    def __init__(self, val=None):
        """ Construct a signal.

        val -- initial value

        """
        self._init = deepcopy(val)
        self._val = deepcopy(val)
        self._next = deepcopy(val)
        self._min = self._max = None
        self._name = self._driven = None
        self._read = self._used = False
        self._inList = False
        self._nrbits = 0
        self._numeric = True
        self._printVcd = self._printVcdStr
        if isinstance(val, bool):
            # we will replace this under the covers by a bit() object
            # replace!
            # print(f'Signal: replacing bool by bit({val})')
            self._init = bit(val)
            self._val = bit(val)
            self._next = bit(val)
            self._type = bit
            self._setNextVal = self._setNextBit
            self._printVcd = self._printVcdBit
            self._nrbits = 1
        elif isinstance(val, bit):
            self._type = bit
            self._setNextVal = self._setNextBit
            self._printVcd = self._printVcdBit
            self._nrbits = 1
        elif isinstance(val, int):
            # if val in [0, 1]:
            #     # print(f'Signal: replacing int 0 | 1 by bit({val})')
            #     self._init = bit(val)
            #     self._val = bit(val)
            #     self._next = bit(val)
            #     self._type = bit
            #     self._setNextVal = self._setNextBit
            #     self._printVcd = self._printVcdBit
            #     self._nrbits = 1
            # else:
                self._type = int
                self._setNextVal = self._setNextInt
        elif isinstance(val, intbv):
            self._type = intbv
            self._min = val._min
            self._max = val._max
            self._nrbits = val._nrbits
            self._setNextVal = self._setNextIntbv
            if self._nrbits:
                self._printVcd = self._printVcdVec
            else:
                self._printVcd = self._printVcdHex
        else:
            self._type = type(val)
            if isinstance(val, EnumItemType):
                self._setNextVal = self._setNextNonmutable
            else:
                self._setNextVal = self._setNextMutable
            if hasattr(val, '_nrbits'):
                self._nrbits = val._nrbits
        self._eventWaiters = _WaiterList()
        self._posedgeWaiters = _PosedgeWaiterList(self)
        self._negedgeWaiters = _NegedgeWaiterList(self)
        self._code = ""
        self._slicesigs = []
        self._tracing = 0
        _signals.append(self)

    def _clear(self):
        del self._eventWaiters[:]
        del self._posedgeWaiters[:]
        del self._negedgeWaiters[:]
        self._val = deepcopy(self._init)
        self._next = deepcopy(self._init)
        self._name = self._driven = None
        self._read = False  # dont clear self._used
        self._inList = False
        self._numeric = True
        for s in self._slicesigs:
            s._clear()

    def _update(self):
        val, next = self._val, self._next
        if val != next:
            waiters = self._eventWaiters[:]
            del self._eventWaiters[:]
            if not val and next:
                waiters.extend(self._posedgeWaiters[:])
                del self._posedgeWaiters[:]
            elif not next and val:
                waiters.extend(self._negedgeWaiters[:])
                del self._negedgeWaiters[:]
            if next is None:
                self._val = None
            elif isinstance(val, intbv):
                self._val._val = next._val
            elif isinstance(val, (int, EnumItemType)):
                self._val = next
            else:
                self._val = deepcopy(next)
            if self._tracing:
                self._printVcd()
            return waiters
        else:
            return []

    # support for the 'val' attribute
    @property
    def val(self):
        return self._val

    # support for the 'next' attribute
    @property
    def next(self):
        #        if self._next is self._val:
        #            self._next = deepcopy(self._val)
        _siglist.append(self)
        return self._next

    @next.setter
    def next(self, val):
        if isinstance(val, _Signal):
            val = val._val
        self._setNextVal(val)
        _siglist.append(self)

    # support for the 'posedge' attribute
    @property
    def posedge(self):
        return self._posedgeWaiters

    # support for the 'negedge' attribute
    @property
    def negedge(self):
        return self._negedgeWaiters

    # support for the 'min' and 'max' attribute
    @property
    def max(self):
        return self._max

    @property
    def min(self):
        return self._min

    # support for the 'driven' attribute
    @property
    def driven(self):
        return self._driven

    @driven.setter
    def driven(self, val):
        if not val in ("reg", "wire", True):
            raise ValueError(f'Expected value "reg", "wire", or True, got "{val}"')
        self._driven = val

    # support for the 'read' attribute
    @property
    def read(self):
        return self._read

    @read.setter
    def read(self, val):
        if not val in (True,):
            raise ValueError(f'Expected value True, got "{val}"')
        self._markRead()

    def _markRead(self):
        self._read = True

    # 'used' attribute
    def _markUsed(self):
        self._used = True

    # set next methods
    def _setNextBit(self, val):
        # only accept boolean values
        if not val in [0, 1, True, False]:
            raise ValueError(f"Expected boolean value, got {repr(val)} ({type(val)})")
        self._next = val

    def _setNextInt(self, val):
        if isinstance(val, intbv):
            val = val._val
        elif not isinstance(val, (int, intbv, bit)):
            raise TypeError(f"Expected int or intbv, got {type(val)}")
        self._next = val

    def _setNextIntbv(self, val):
        if isinstance(val, intbv):
            val = val._val
        elif not isinstance(val, int):
            raise TypeError(f"Expected int or intbv,  got {type(val)}")
        self._next._val = val
        self._next._handleBounds()

    def _setNextNonmutable(self, val):
        if not isinstance(val, self._type):
            raise TypeError(f"Expected {self._type}, got {type(val)}")
        self._next = val

    def _setNextMutable(self, val):
        if not isinstance(val, self._type):
            raise TypeError(f"Expected {self._type}, got {type(val)}")
        self._next = deepcopy(val)

    # vcd print methods
    def _printVcdStr(self):
        print(f"s{str(self._val)} {self._code}", file=sim._tf)

    def _printVcdHex(self):
        if self._val is None:
            print(f"sz {self._code}", file=sim._tf)
        else:
            print(f"s{hex(self._val)} {self._code}", file=sim._tf)

    def _printVcdBit(self):
        if self._val is None:
            print(f"z{self._code}" % self._code, file=sim._tf)
        else:
            print(f"{self._val}{self._code}" % (self._val, self._code), file=sim._tf)

    def _printVcdVec(self):
        if self._val is None:
            print(f"b{'z' * self._nrbits} {self._code}", file=sim._tf)
        else:
            print(f"b{bin(self._val, self._nrbits)} {self._code}", file=sim._tf)

    ### use call interface for shadow signals ###
    def __call__(self, left, right=None):
        s = _SliceSignal(self, left, right)
        self._slicesigs.append(s)
        return s

    ### operators for which delegation to current value is appropriate ###

    def __hash__(self):
        raise TypeError("Signals are unhashable")

    def __bool__(self):
        return bool(self._val)

    __nonzero__ = __bool__

    # length
    def __len__(self):
        return self._nrbits
        # return len(self._val)

    # indexing and slicing methods

    def __getitem__(self, key):
        return self._val[key]

    # integer-like methods

    def __add__(self, other):
        if isinstance(other, _Signal):
            return self._val + other._val
        else:
            return self._val + other

    def __radd__(self, other):
        return other + self._val

    def __sub__(self, other):
        if isinstance(other, _Signal):
            return self._val - other._val
        else:
            return self._val - other

    def __rsub__(self, other):
        return other - self._val

    def __mul__(self, other):
        if isinstance(other, _Signal):
            return self._val * other._val
        else:
            return self._val * other

    def __rmul__(self, other):
        return other * self._val

    def __truediv__(self, other):
        if isinstance(other, _Signal):
            return self._val / other._val
        else:
            return self._val / other

    def __rtruediv__(self, other):
        return other / self._val

    def __floordiv__(self, other):
        if isinstance(other, _Signal):
            return self._val // other._val
        else:
            return self._val // other

    def __rfloordiv__(self, other):
        return other // self._val

    def __mod__(self, other):
        if isinstance(other, _Signal):
            return self._val % other._val
        else:
            return self._val % other

    def __rmod__(self, other):
        return other % self._val

    # XXX divmod

    def __pow__(self, other):
        if isinstance(other, _Signal):
            return self._val ** other._val
        else:
            return self._val ** other

    def __rpow__(self, other):
        return other ** self._val

    def __lshift__(self, other):
        if isinstance(other, _Signal):
            return self._val << other._val
        else:
            return self._val << other

    def __rlshift__(self, other):
        return other << self._val

    def __rshift__(self, other):
        if isinstance(other, _Signal):
            return self._val >> other._val
        else:
            return self._val >> other

    def __rrshift__(self, other):
        return other >> self._val

    def __and__(self, other):
        if isinstance(other, _Signal):
            return self._val & other._val
        else:
            return self._val & other

    def __rand__(self, other):
        return other & self._val

    def __or__(self, other):
        if isinstance(other, _Signal):
            return self._val | other._val
        else:
            return self._val | other

    def __ror__(self, other):
        return other | self._val

    def __xor__(self, other):
        if isinstance(other, _Signal):
            return self._val ^ other._val
        else:
            return self._val ^ other

    def __rxor__(self, other):
        return other ^ self._val

    def __neg__(self):
        return -self._val

    def __pos__(self):
        return +self._val

    def __abs__(self):
        return abs(self._val)

    def __invert__(self):
        return ~self._val

    # conversions

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
        return self.val == other

    def __ne__(self, other):
        return self.val != other

    def __lt__(self, other):
        return self.val < other

    def __le__(self, other):
        return self.val <= other

    def __gt__(self, other):
        return self.val > other

    def __ge__(self, other):
        return self.val >= other

    # method lookup delegation
    def __getattr__(self, attr):
        return getattr(self._val, attr)

    # representation
    def __str__(self):
        if self._name:
            return self._name
        else:
            return str(self._val)

    def __repr__(self):
        if self._name:
            return f'{self._name} = Signal({repr(self._val)})'
        else:
            return f"Signal({repr(self._val)})"

    def _toVerilog(self):
        return self._name

    # augmented assignment not supported
    def _augm(self):
        raise TypeError("Signal object doesn't support augmented assignment")

    __iadd__ = __isub__ = __imul__ = __ipow__ = __imod__ = _augm
    __ior__ = __iand__ = __ixor__ = __irshift__ = __ilshift__ = _augm
    __itruediv__ = __ifloordiv__ = _augm

    # index and slice assignment not supported
    def __setitem__(self, key, val):
        raise TypeError("Signal object doesn't support item/slice assignment")

    # continuous assignment support
    def assign(self, sig):

        self.driven = "wire"

        def genFunc():
            while 1:
                self.next = sig._val
                yield sig

        self._waiter = _SignalWaiter(genFunc())

        def toVHDL():
            return f"{self._name} <= {sig._name};"

        def toVerilog():
            return f"assign {self._name} = {sig._name};"

        self.toVHDL = toVHDL
        self.toVerilog = toVerilog


class _DelayedSignal(_Signal):

    __slots__ = ('_nextZ', '_delay', '_timeStamp',)

    def __init__(self, val=None, delay=1):
        """ Construct a new DelayedSignal.

        Automatically invoked through the Signal new method.
        val -- initial value
        delay -- non-zero delay value
        """
        _Signal.__init__(self, val)
        self._nextZ = val
        self._delay = delay
        self._timeStamp = 0

    def _update(self):
        if self._next != self._nextZ:
            self._timeStamp = sim._time
        self._nextZ = self._next
        t = sim._time + self._delay
        _schedule((t, _SignalWrap(self, self._next, self._timeStamp)))
        return []

    def _apply(self, next, timeStamp):
        val = self._val
        if timeStamp == self._timeStamp and val != next:
            waiters = self._eventWaiters[:]
            del self._eventWaiters[:]
            if not val and next:
                waiters.extend(self._posedgeWaiters[:])
                del self._posedgeWaiters[:]
            elif not next and val:
                waiters.extend(self._negedgeWaiters[:])
                del self._negedgeWaiters[:]
            self._val = copy(next)
            if self._tracing:
                self._printVcd()
            return waiters
        else:
            return []

    # support for the 'delay' attribute
    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, delay):
        self._delay = delay


class _SignalWrap(object):

    def __init__(self, sig, next, timeStamp):
        self.sig = sig
        self.next = next
        self.timeStamp = timeStamp

    def apply(self):
        return self.sig._apply(self.next, self.timeStamp)


class Constant(_Signal):
    ''' effective constants '''

    def __init__(self, val=None):
        super(Constant, self).__init__(val)

    # override some essentials
    def __repr__(self):
        return f"Constant({repr(self._val)})"

    # there is support for the 'next' attribute
    @property
    def next(self):
        return None

    @next.setter
    def next(self, val):
        raise PermissionError("A 'Constant' can not be changed!")

    # neither can it be driven
    # support for the 'driven' attribute
    @property
    def driven(self):
        return None

    @driven.setter
    def driven(self, val):
        # quietly ignore?
        pass


# for export
SignalType = _Signal

# avoid circular imports

from myhdl._ShadowSignal import _SliceSignal
from myhdl._Waiter import _SignalWaiter
from myhdl._enum import EnumItemType

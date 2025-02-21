#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2013 Jan Decaluwe
#  Copyright (C) 2025 Josy Boelen
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
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

'''
Created on 20 jan. 2025

@author: josy
'''

import math
import re
import warnings

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl._intbv import intbv

re_u1 = re.compile(r"\d+\.\d+\.\d+")
re_u2 = re.compile(r"\d+\.\d+")
re_q = re.compile(r"Q\d+\.\d+")
re_uq = re.compile(r"UQ\d+\.\d+")
re_str = re.compile(r"[+ | -]*[0 | 1 | _]*\.[0 | 1 | _]+")


class _FixbvResult(object):

    def __init__(self, real=None, vector=None):
        self.real = real
        self.vector = vector

    def __repr__(self):
        return f"_FixbvResult(real={self.real}, vector={self.vector})"

    def __add__(self, other):
        assert isinstance(other, _FixbvResult)
        return _FixbvResult(self.real + other.real, self.vector + other.vector)

    __radd__ = __add__


class fixbv(intbv):
    '''
        an implementation *slighty* based on MEP 111
        with modifications
        we decide to not use the res=0.1 method as this is a bit opaque about what happens in HW
        and find the inverse, 'fractionalbits' a better (explicit) way
        
        we present a novel idea: 
        in simulation we keep track of both the **real** value ( represented by `float` in Python's case) 
        and the **integer bitvector** representation
            the *min* and *max* limits for the integer representation are set to the physical limits:
            signed: `-2 ** (wl - 1)` and `2 ** (wl -1)` with `wl = wi + wf` where *wi* includes the optional sign bit
            unsigned: 0, 2 ** wl with again `wl = wi + wf` but obviously without a sign bit
            as the integer part is modelled by subclassing `modbv` it will mimic what happens in hardware; nicely wrap around
            
            the real value being a `float` follows the language's rules :)
            
            the `handlebounds()` method will not check the integer value, as in the `intbv' class, but the `float` limits
            optionally compare the value of the integer bit representation to the tracked real value and will issue a warning, 
            not an exception, if this differs more than a given **delta**
            
            the (optional) .vcd trace will output both the integer and the real representation.
        
    '''

    def __init__(self, val=0.0, fmin=None, fmax=None, fractionalbits=None, spec=None, delta=None):
        '''
            we allow for '50 ways to leave your lover'
            fval: int | float: <(fmin, fmax, fractionalbits) | spec> are required
                  str : '-bbb.bbb_bbbb_bbbb_bbbb'
                        with b in [0,1], the minus sign is ofcourse 'optional'
                        a plus sign is also allowed
                        allowing underscores to increase readabiltiy
                        neither fmin, fmax, fractionalbits  nor 'spec' are needed in this case
                        although fmin and fmax can be specified for simulation purposes
                        
            spec: we accept:
                'Qi.f'  : signed fixed point, width = i + f; see https://en.wikipedia.org/wiki/Q_(number_format)
                          !!! 'i' includes the sign bit
                'UQi.f' : unsigned fixed point, width = i + f
                'i.f'   : unsigned fixed point, width = i + f
                '0.i.f' : unsigned fixed point, width = i + f
                '1.i.f' : signed fixed point, width = 1 + i + f
                or 'None'  : then must/may have to specify min, max and fractionalbits
                
            Advance use:
                we can accept a tuple of two fixbv accompagnied with an operator to create a new fixbv
                as in e.g.: ( D, '*', K) , (A, '+', B)
        '''
        signed = False
        if isinstance(val, tuple):
            assert len(val) == 3
            assert val[1] in ('+', '-', '*', '/', '//', '**')
            la = val[0] if isinstance(val[0], fixbv) else val[0]._val
            ra = val[2] if isinstance(val[2], fixbv) else val[2]._val
            assert isinstance(la, fixbv) and isinstance(ra, fixbv)

            if val[1] == '*':
                # we can simply add up the lengths; this will define imax and imin
                wi = la._wi + ra._wi
                wf = la._wf + ra._wf
                # probably 0.0 most of the time
                fval = la._fval * ra._fval
                # but fmin and fmax are a bit more complicated
                # at least one is signed ->
                # fmin = min(l.m * r.M, l.M * r.m)
                # fmax = max(l.m * r.m, l.M * r.M)
                # -3.0, 4.0 * -4.0, 5.0 -> min(-15.0, -16.0), max(12.0, 20.0)
                # -3.0, 4.0 * -4.0, 0.0 -> min(  0.0, -16.0), max(12.0,  0.0)
                # -3.0, 4.0 *  0.0, 6.0 -> min(-18.0,   0.0), max( 0.0, 24.0)
                # -3.0, 4.0 *  1.0, 6.0 -> min(-18.0,  -3.0), max(-3.0, 24.0)
                # -3.0, 0.0 * -4.0, 5.0 -> min(-15.0,   0.0), max(12.0,  0.0)
                # -3.0, 0.0 *  0.0, 6.0 -> min(-18.0,   0.0), max( 0.0,  0.0)
                # -3.0, 0.0 *  1.0, 6.0 -> min(-18.0,   0.0), max(-3.0,  0.0)
                # two unsigned ->
                # fmin = l.m * r.m
                # fmax = l.M * r.M
                #  0.0, 2.0 *  0.0, 7.0 -> min(  0.0,   0.0), max( 0.0, 14.0)

                if la._signed or ra._signed:
                    signed = True
                    # one or both is signed
                    fmin = min(la._fmin * ra._fmax, la._fmax * ra._fmin)
                    fmax = max(la._fmin * ra._fmin, la._fmax * ra._fmax)

                else:
                    # none is signed
                    fmin = la._fmin * ra._fmin
                    fmax = la._fmax * ra._fmax

            elif val[1] == '+':
                # select the largest fractional part
                wf = max(la._wf, ra._wf)
                # may have to grow the largest integer part
                wi = int(math.ceil(math.log2(max(la._fmax + ra._fmax, -(la._fmin + ra._fmin)))))
                if la._fmin + ra._fmin < 0:
                    wi += 1
                    signed = True
                # compute fmin, fmax
                fmin = la._fmin + ra._fmin
                fmax = la._fmax + ra._fmax
                fval = la._fval + ra._fval
            else:
                raise ValueError(f"fixbv({val}: operator {val[1]} not implemented")

            wl = wi + wf
            # TODO: disable _fval checking (for now)?
            delta = None

        elif isinstance(val, str):
            hassign = False
            # expect a string like: '-bbb.bbb_bbbb_bbbb_bbbb'
            assert re_str.match(val)
            if val[0] in ('+', '-'):
                if val[0] == '-':
                    hassign = True
                tval = val[1:].replace('_', '')

            else:
                tval = val.replace('_', '')

            i, __ , f = tval.partition('.')
            if hassign or (fmin and fmin < 0):
                signed = True
            # ! the `int` part may be empty ...
            wi = len(i) + (1 if signed else 0)
            wf = len(f)
            wl = wi + wf
            if i:
                fval = int(i, 2) + int(f, 2) / (2 ** wf)
            else:
                fval = int(f, 2) / (2 ** wf)
            if hassign:
                fval = -fval

        elif isinstance(val, fixbv):
            return fixbv(0.0, val._fmin, val._fmax, val._wf)

        else:
            if isinstance(val, int):
                fval = float(val)

            else:
                assert isinstance(val, float)
                fval = val

            if spec is None:
                assert fractionalbits is not None
                wf = fractionalbits
                assert fmin is not None
                assert fmax is not None
                if fmin < 0 or val < 0:
                    signed = True
                if fval == fmax:
                    # # must add minimal head-room to let _handleBounds pass?
                    # fmax += 1 / (2 ** wf)
                    raise ValueError(f"fixbv({val}, {fmin}, {fmax}, {fractionalbits}): val {val} must be less than fmax {fmax}")

                assert fmin < fmax
                tmax = max(fmax, abs(fmin))
                wi = int(math.ceil(math.log2(tmax)))
                if 2 ** wi == int(abs(fmin)):
                    wi += 1
                wl = wi + wf

            else:
                # well defined
                # need some re-magic?
                if re_u1.match(spec):
                    s, __ , r = spec.partition('.')
                    signed = (s == '1')
                    i, __ , f = r.partition('.')
                    wi = int(i) + (1 if signed else 0)
                    wf = int(f)
                    wl = wi + wf

                elif re_u2.match(spec):
                    i, __ , f = spec.partition('.')
                    wi = int(i)
                    wf = int(f)
                    wl = wi + wf

                elif re_q.match(spec):
                    signed = True
                    i, __ , f = spec[1:].partition('.')
                    wi = int(i)
                    wf = int(f)
                    wl = wi + wf

                elif re_uq.match(spec):
                    i, __ , f = spec[2:].partition('.')
                    wi = int(i)
                    wf = int(f)
                    wl = wi + wf

                else:
                    raise ValueError(f'fixbv: Unknown specification: {spec}')

                # update fmin and fmax, setting them to the limits
                fmin = float(-2 ** (wi - 1) if signed else 0)
                fmax = float(2 ** (wi - 1) if signed else 2 ** wi)

        ival = int(fval * (2 ** wf))
        imin = -2 ** (wl - 1) if signed else 0
        imax = 2 ** (wl - 1)  if signed else 2 ** wl

        # add a `real` for simulation
        self._fval = fval
        self._signed = signed
        self._fmin = fmin
        self._fmax = fmax
        self._delta = delta
        self._wl = wl
        self._wi = wi
        self._wf = wf
        self._SCALE = 2 ** self._wf

        # we must call upon our parent - which is not modbv but intbv
        super(fixbv, self).__init__(ival, imin, imax)

    def _hasFullRange(self):
        return True  # by design

    def _handleBounds(self):
        # copied over from modbv
        # the vector part wraps around
        lo, hi, val = self._min, self._max, self._val
        if lo is not None:
            if val < lo or val >= hi:
                self._val = (val - lo) % (hi - lo) + lo

        # but we check on the `float` limits
        if self._fmax is not None:
            if self._fval >= self._fmax:
                raise ValueError(f"intbv value {self._fval} >= maximum {self._fmax}")
        if self._fmin is not None:
            if self._fval < self._fmin:
                raise ValueError(f"intbv value {self._fval} < minimum {self._fmin}")

        # checking?
        if self._delta:
            if  abs(self._fval - self._val / self._SCALE) > self._delta:
                warnings.warn(
                        f"\n    fixbv: difference between real({self.real}) and integer({self._val / (2**self._wf)} > {self._delta} ",
                        category=UserWarning,
                        stacklevel=2,
                        )

    def __deepcopy__(self, visit):
        return type(self)(self._fval, self._fmin, self._fmax, self._wf)

    def __copy__(self):
        return type(self)(self._fval, self._fmin, self._fmax, self._wf)

    def __repr__(self):
        return f"fixbv({self._fval}, fmin={self._fmin}, fmax={self._fmax}, fractionalbits={self._wf})"

    @property
    def info(self):
        return (f"fixbv: fval={self._fval}, fmin={self._fmin}, fmax={self._fmax}, fractionalbits={self._wf}, intbits={self._wi},"
                f"val={self._val}, min={self._min}, max={self._max}, nrbits={self._nrbits}")

    def __int__(self):
        return self._val >> self._wf

    def __float__(self):
        return self._fval

    @property
    def float(self):
        return self._fval

    @property
    def int(self):
        return self._val >> self._wf

    @property
    def frac(self):
        return self._val & (self._SCALE - 1)

    @property
    def ord(self):
        return self._val

    @property
    def spec(self):
        return (self._wi, self._wf)

    @property
    def fractionalbits(self):
        return self._wf

    def __getitem__(self, key):
        '''
            __getitem__ works on the vector representation
        '''
        if isinstance(key, slice):
            left = key.start
            right = key.stop
            # assume there is no key.step ...
            rv = _FixbvResult()
            if left is None:
                # s[:R]
                # this means we are truncating on the right of the fraction bits
                # the real value is thus unchanged
                rv.real = self._fval
                if right < 0:
                    right += self._wl
                rv.vector = self._val >> int(right)
            else:
                # s[L:] or s[L:R]
                # first truncate on the left
                left = int(left)
                tl = left if left > 0 else (self._wl + left)
                rv.vector = self._val & (2 ** tl - 1)
                twf = self._wf
                if right is not None:
                    # also cutting on the right side
                    right = int(right)
                    tr = right if right > 0 else (self._wl + right)
                    rv.vector >>= tr
                    twf -= tr

                # we must check whether the actual real value fits in the left-truncated
                # if not we return the trusted NaN
                if self._signed:
                    treal = rv.vector / (2 ** (twf - 1))
                    if -treal <= self._fval < treal:
                        rv.real = self._fval
                    else:
                        # TODO: the NaN may not be the ideal thing?
                        # doesn't fit
                        rv.real = math.nan

                else:
                    if self._fval < rv.vector / (2 ** twf):
                        rv.real = self._fval
                    else:
                        # TODO: the NaN may not be the ideal thing?
                        # doesn't fit
                        rv.real = math.nan

            return rv

        else:
            # s[I]
            # for 'rounding' operations
            # we return 0.0 for the 'real' value
            # rationale:
            #    say that after a multiplication you want to reduce the fractional width
            #    adding the highest bit of that cut-off part of the fraction will round
            #    the int value to the nearest lowest bit
            #    but the real result of the multiplication is correct (being the result of `float` * `float`)
            #    and thus we should not add anything to it
            # same applies when adding two fixbv, the `float` part will always be correct
            if key < 0:
                key += self._wl
            return _FixbvResult(0.0, (self._val >> int(key)) & 0x1)

    def __setitem__(self, key, val):
        raise NotImplementedError(f"{repr(self)}[{key}] = {val}: cannot set bits in the bitvector " \
                                  "as that will invalidate the tracked *real* value")

    # integer-like methods
    def _addsubvalidate(self, other):
        ''' helper: validate the other to comply for addition or subtraction '''
        if isinstance(other, fixbv):
            if other._wf < self._wf:
                return _FixbvResult(other._fval, other._val << (self._wf - other._wf))
            elif other._wf > self._wf:
                return _FixbvResult(other._fval, other._val >> (other._wf - self._wf))
            else:
                return _FixbvResult(other._fval, other._val)

        elif isinstance(other, intbv):
            return _FixbvResult(float(other._val), other._val)

        elif isinstance(other, bool):
            bi = int(other)
            return _FixbvResult(float(bi), bi)

        elif isinstance(other, int):
            return _FixbvResult(float(other), other)
        elif isinstance(other, float):
            return _FixbvResult(other, int(other * self._SCALE))
        elif isinstance(other, _FixbvResult):
            return other
        else:
            raise ValueError(f"Cannot handle {repr(other)} for fixbv `add` or `sub` operation")

    def __add__(self, other):
        rr = self._addsubvalidate(other)
        return _FixbvResult(self._fval + rr.real, self._val + rr.vector)

    __radd__ = __add__

    def __sub__(self, other):
        rr = self._addsubvalidate(other)
        return _FixbvResult(self._fval - rr.real, self._val - rr.vector)

    def __rsub__(self, other):
        rr = self._addsubvalidate(other)
        return _FixbvResult(rr.real - self._fval, rr.vector - self._val)

    def _muldivvalidate(self, other):
        ''' helper: validate the other to comply for multiplication (or division too?) '''
        if isinstance(other, fixbv):
            return _FixbvResult(other._fval, other._val)

        elif isinstance(other, intbv):
            return _FixbvResult(float(other._val), other._val)

        elif isinstance(other, bool):
            bi = int(other)
            return _FixbvResult(float(bi), bi)

        elif isinstance(other, int):
            return _FixbvResult(float(other), other * self._SCALE)
        elif isinstance(other, float):
            return _FixbvResult(other, int(other * self._SCALE))
        elif isinstance(other, _FixbvResult):
            return other
        else:
            raise ValueError(f"Cannot handle {repr(other)} for fixbv `mul` or `div` operation")

    def __mul__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(self._fval * rr.real, self._val * rr.vector)

    __rmul__ = __mul__

    def __truediv__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(self._fval / rr.real, int(self._SCALE * self._val / rr.vector))

    def __rtruediv__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(rr.real / self._fval, int(self._SCALE * rr.vector / self._val))

    def __floordiv__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(self._fval / rr.real, int(self._SCALE * self._val // rr.vector))

    def __rfloordiv__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(rr.real // self._fval, int(self._SCALE * rr.vector // self._val))

    def __mod__(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(self._fval % rr.real, self._val % rr.vector)

    def rmod(self, other):
        rr = self._muldivvalidate(other)
        return _FixbvResult(rr.real % self._fval, rr.vector % self._val)

    def __pow__(self, other):
        raise ArithmeticError(f"Do not support `pow` operation for fixbv")

    __rpow__ = __pow__

    # we leave the comparison, shift and logical operations to our `intbv` 'base' class
    # assuming that the  result will NOT be assigned to a fixbv type ...


if __name__ == '__main__':
    import sys
    from myhdl import Signal

    def printexception(e):
        print(f'Exception: {e}')

    t0 = fixbv(math.pi, spec='2.16')
    t1 = fixbv(math.pi, spec='0.2.16')
    t2 = fixbv(-math.pi, spec='1.2.15')
    t3 = fixbv(-math.pi, spec='Q3.15')
    t4 = fixbv(math.pi, spec='UQ3.15')
    t5 = fixbv('-11.001_0010_0001_1111')
    t6 = fixbv('11.0010_0100_0011_1111')
    t7 = fixbv(0.0, -0.99, 0.99, 16)
    t9 = fixbv('.0010_0100_0011_1111')
    t10 = fixbv('.0010_0100_0011_1111', fmin=-0.5, fmax=0.8)
    t11 = fixbv(math.pi, fmin=-8, fmax=8, fractionalbits=12)
    t12 = fixbv(0.0, fmin=-0.99, fmax=sys.float_info.epsilon, fractionalbits=16)
    t13 = fixbv((-1 + math.sqrt(5)) / 2, spec='UQ0.18')
    t14 = fixbv(1.0, spec='1.17')
    ic(t0, repr(t0), isinstance(t0, fixbv))
    ic(t0 * t1)
    ic(t0 / t1)
    ic(t0 / 2)
    ic(t0 // 2)
    ic(1 / t0)
    ic(t14 / t0)
    ic(repr(t13), t13._val)
    ic((1 / t13) - t13)
    ic((1 / t13) * t13)
    ic(t6, t6.int, t6.frac, t6.ord)
    ic(t5, t5.int)
    ic(t0 == t1, t0 == t2, t0 > t2, t1 + t2, t2 + t1, t0 + 1, 1 + t0, 12.34 + t0)

    s0 = Signal(t0)
    ic(s0, s0._type)
    s1 = Signal(intbv(0, _nrbits=16))
    ic(s1)

    # this doesn't seem to work, but does if executed in a console ...
    # s0.next = 6.0
    # ic(s0, s0.next)
    # s0.update()
    # ic(s0)
    ic(t0, t0.ord, t0[:1], t0[-1:], t0[17:], t0[:-17])
    ic(t2, t2.ord, t2[:1], t2[-1:], t2[-1])
    try:
        t2[6:] = 42
    except NotImplementedError as e:
        printexception(e)

    try:
        t14[5] = 0
    except NotImplementedError as e:
        printexception(e)

    t15 = fixbv(1.234, -1.0, 2.0, 16)
    t16 = fixbv(1.234, -2.0, 4.0, 16)
    t18 = fixbv(1.0, 0.0, 5.0, 14)
    t20 = fixbv(-1.0, -2.0, -0.5, 12)
    ic(t15, t16, t18, t20)
    ic(fixbv((t15, '*', t16)))
    ic(fixbv((t15, '*', t18)))
    ic(fixbv((t18, '*', t20)))
    t21 = fixbv((t18, '+', t20))
    ic(t21, t21._wi, t21._wf)
    ic((t22 := fixbv((t15, '+', t16))), t22._wi, t22._wf)
    ic(t22.info)

    t23 = fixbv(0.0, -5.0, 1.0, 16)
    t24 = fixbv(0.0, -8.0, 8.0, 16)
    ic(t23.info, t24.info)

    try:
        t25 = fixbv(8.0, -8.0, 8.0, 16)
    except ValueError as e:
        printexception(e)

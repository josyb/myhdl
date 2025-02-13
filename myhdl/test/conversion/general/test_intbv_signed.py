#!/usr/bin/env python
#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2008 Jan Decaluwe
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

""" Run the intbv.signed() unit tests. """
from myhdl import (block, intbv, delay, concat, instance, conversion)


@block
def PlainIntbv():
    '''Test a plain intbv instance with .signed() 

    ----+----+----+----+----+----+----+----
       -3   -2   -1    0    1    2    3

                      min  max
                           min  max
                 min       max
                 min            max
            min            max
            min       max
            min  max
          neither min nor max is set
          only max is set
          only min is set

    '''
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # in the following cases the .signed() function should classify the
    # value of the intbv instance as unsigned and return the 2's
    # complement value of the bits as specified by _nrbits.
    #

    @instance
    def comb():

        print("Plain Instance Test")

        yield delay(10)
        # intbv with positive range, pos number, and msb not set, return signed()
        # Expect the number to be returned
        a1 = intbv(0x3b, min=0, max=0x7c)
        b1 = a1.signed()
        assert b1 == 0x3b

        # intbv with positive range, pos number, and msb set, return signed()
        # test various bit patterns to see that the 2's complement
        # conversion works correct
        # Expect the number to be converted to a negative number
        a2 = intbv(7, min=0, max=8)
        b2 = a2.signed()
        assert b2 == -1

        a3 = intbv(6, min=0, max=8)
        b3 = a3.signed()
        assert b3 == -2

        a4 = intbv(5, min=0, max=8)
        b4 = a4.signed()
        assert b4 == -3

        # set bit #3 and increase the range so that the set bit is considered
        # the sign bit. Here min = 0
        # Expect to return -4
        a5 = intbv(4, min=0, max=5)
        b5 = a5.signed()
        assert b5 == -4

        a6 = intbv(4, min=0, max=6)
        b6 = a6.signed()
        assert b6 == -4

        a7 = intbv(4, min=0, max=7)
        b7 = a7.signed()
        assert b7 == -4

        a8 = intbv(4, min=0, max=8)
        b8 = a8.signed()
        assert b8 == -4

        # here it is not the sign bit anymore
        # Expect the value to be 4
        a9 = intbv(4, min=0, max=9)
        b9 = a9.signed()
        assert b9 == 4

        # set bit #3 and increase the range so that the set bit is considered
        # the sign bit. Here min > 0
        # Expect to return -4
        a10 = intbv(4, min=1, max=5)
        b10 = a10.signed()
        assert b10 == -4

        a11 = intbv(4, min=2, max=6)
        b11 = a11.signed()
        assert b11 == -4

        a12 = intbv(4, min=3, max=7)
        b12 = a12.signed()
        assert b12 == -4

        a13 = intbv(4, min=4, max=8)
        b13 = a13.signed()
        assert b13 == -4

        # again with min > 0, here it is not the sign bit anymore
        # Expect the value to be 4
        a14 = intbv(4, min=2, max=9)
        b14 = a14.signed()
        assert b14 == 4

        # intbv with positive range, value = 0, return signed()
        # Expect the number to be returned
        a15 = intbv(0, min=0, max=0x8)
        b15 = a15.signed()
        assert b15 == 0

        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # in these cases the .signed() function should classify the
        # value of the intbv instance as signed and return the value as is
        #

        # set bit #3 and increase the range that the set bit is actually the
        # msb, but due to the negative range not considered signed
        # Expect to return 4
        a20 = intbv(4, min=-1, max=5)
        b20 = a20.signed()
        assert b20 == 4

        a21 = intbv(4, min=-1, max=6)
        b21 = a21.signed()
        assert b21 == 4

        a22 = intbv(4, min=-1, max=7)
        b22 = a22.signed()
        assert b22 == 4

        a23 = intbv(4, min=-1, max=8)
        b23 = a23.signed()
        assert b23 == 4

        # intbv with negative range, pos number, and msb set, return signed()
        # Expect the number to returned as is
        a24 = intbv(7, min=-1, max=8)
        b24 = a24.signed()
        assert b24 == 7

        a25 = intbv(6, min=-1, max=8)
        b25 = a25.signed()
        assert b25 == 6

        a26 = intbv(5, min=-1, max=8)
        b26 = a26.signed()
        assert b26 == 5

        # intbv with symmetric (min = -max) range, pos value, msb set
        # return signed()
        # Expect value returned as is
        a27 = intbv(4, min=-8, max=8)
        b27 = a27.signed()
        assert b27 == 4

        # intbv with symmetric (min = -max) range, neg value,
        # return signed()
        # Expect value returned as is
        a28 = intbv(-4, min=-8, max=8)
        b28 = a28.signed()
        assert b28 == -4

        # intbv with symmetric (min=-max) range, value = 0,
        # return signed()
        # Expect value returned as is
        a29 = intbv(0, min=-8, max=8)
        b29 = a29.signed()
        assert b29 == 0

    return comb


@block
def SlicedSigned():
    '''Test a slice with .signed()

    This test can actually be simplified, as a slice will always have
    min=0 and max > min, which will result in an intbv instance that
    will be considered unsigned by the intbv.signed() function.
    '''

    @instance
    def comb():
        b = intbv(4, min=-8, max=8)
        a = intbv(4, min=-8, max=8)
        print("SLicedSigned test")
        yield delay(10)
        b[:] = a[4:]
        assert b == 4
        b[:] = a[4:].signed()
        assert b == 4  # msb is not set with a 4 bit slice

        b[:] = a[3:]
        assert b == 4
        b[:] = a[3:].signed()
        assert b == -4  # msb is set with 3 bits sliced

    return comb


@block
def SignedConcat():
    '''Test the .signed() function with the concatenate function'''

    @instance
    def comb():
        print("Signed Concat test")
        yield delay(10)

        # concat 3 bits
        # Expect the signed function to return a negative value
        a = intbv(0)[3:]
        a[:] = concat(True, True, True)
        assert a == 7
        assert a.signed() == -1
        assert concat(True, True, True).signed() == -1

        # concat a 3 bit intbv with msb set and two bits
        # Expect a negative number
        b = intbv(5, min=0, max=8)
        assert concat(b, True, True).signed() == -9

    return comb


def test_PlainIntbv():
    assert conversion.verify(PlainIntbv()) == 0


def test_SlicedSigned():
    assert conversion.verify(SlicedSigned()) == 0


def test_SignedConcat():
    assert conversion.verify(SignedConcat()) == 0


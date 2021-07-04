'''
Created on 4 jul. 2021

@author: josy
'''
#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2021 Jan Decaluwe
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

from myhdl import (Signal, intbv, block, always_seq, always_comb, Parameter,
                   instances)


class Counter(object):
    ''' a parameterised (simple) counter '''

    def __init__(self, WIDTH, Clk, Reset, SClr, CntEn, Q=None):
        '''
            WIDTH: either int or Parameter()
            Clk, Reset: as usual
            SClr: synchronously clears the counter to 0
            CntEn: enables counting
            Q: id the output of the counter
        '''
        self.WIDTH = WIDTH
        self.Clk = Clk
        self.Reset = Reset
        self.SClr = SClr
        self.CntEn = CntEn
        if Q is not None:
            assert len(Q) == int(WIDTH)
            self.Q = Q
        else:
            self.Q = Signal(intbv(0, _nrbits=WIDTH))

    @block
    def rtl(self):
        ''' the logic '''
        COUNT_MAX = 2 ** int(self.WIDTH) - 1
        counter = Signal(intbv(0, _nrbits=self.WIDTH))

        @always_seq(self.Clk.posedge, reset=self.Reset)
        def count():
            if self.SClr or self.CntEn:
                if self.SClr:
                    counter.next = 0
                else:
                    if counter < COUNT_MAX:
                        counter.next = counter + 1
                    else:
                        counter.next = 0

        @always_comb
        def mkoutput():
            self.Q.next = counter

        return instances()


if __name__ == '__main__':
    from myhdl import ResetSignal, instance, delay, StopSimulation

    @block
    def tb_Counter():
        T_WIDTH = Parameter('WIDTH', 4)
        Clk = Signal(bool(0))
        Reset = ResetSignal(0, 1, False)
        SClr = Signal(bool(0))
        CntEn = Signal(bool(0))

        dut = Counter(T_WIDTH, Clk, Reset, SClr, CntEn)
        dutrtl = dut.rtl()
        dutrtl.name = 'Counter'

        tCK = 10

        @instance
        def genclk():
            while True:
                yield delay(tCK // 2)
                Clk.next = not Clk

        @instance
        def genreset():
            Reset.next = 1
            yield delay(int(tCK * 3.5))
            Reset.next = 0

        @instance
        def stimulus():
            yield delay(tCK * 5)
            yield Clk.posedge
            yield delay(tCK // 4)
            SClr.next = 1
            yield Clk.posedge
            yield delay(tCK // 4)
            SClr.next = 0
            yield Clk.posedge
            yield Clk.posedge
            yield delay(tCK // 4)
            CntEn.next = 1
            yield delay(tCK * 20)
            yield Clk.posedge
            yield delay(tCK // 4)
            CntEn.next = 0

            yield delay(tCK * 5)
            raise StopSimulation

        return instances()

    @block
    def top_Counter(WIDTH, Clk, Reset, SClr, CntEn, Q):
        return Counter(WIDTH, Clk, Reset, SClr, CntEn, Q).rtl()

    def convert():
        C_WIDTH = Parameter('WIDTH', 8)
        # C_WIDTH = 7
        Clk = Signal(bool(0))
        Reset = ResetSignal(0, 1, False)
        SClr = Signal(bool(0))
        CntEn = Signal(bool(0))
        Q = Signal(intbv(0, _nrbits=C_WIDTH))

        dfc = top_Counter(C_WIDTH, Clk, Reset, SClr, CntEn, Q)
        dfc.convert(hdl='VHDL')

    dft = tb_Counter()
    dft.config_sim(trace=True)
    dft.run_sim()

    convert()

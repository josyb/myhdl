'''
Created on 30 okt. 2023

@author: josy
'''
from myhdl import (block, Signal, intbv, modbv, always_comb, always_seq , Constant,
                   instances)

''' testing simple always comb '''


@block
def sac(a, b, c):
    ''' continuous assignments '''

    @always_comb
    def comb():
        ''' this is a continuous assignment '''
        c.next = a and not b

    return comb


@block
def sac2(a, b, c, d , e):
    ''' more continuous assignments '''

    @always_comb
    def comb():
        ''' this are continuous assignments '''
        d.next = a and not b
        e.next = not a and b
        ''' reading back outputs, oh no? '''
        c.next = a or b or d or e

    return comb


@block
def sac3(a, b):

    @always_comb
    def comb():
        b.next = a[0] and not a[1]

    return comb


@block
def sac4(a, b):
    ''' an always_comb '''

    LEN_V = len(a)

    @always_comb
    def comb():
        ''' an always_comb '''
        b.next = 0
        ''' looping '''
        for i in range(LEN_V):
            b.next = b or a[i]

    return comb


@block
def sac5(a, b , c):

    @always_comb
    def comb():
        b.next = a[0]
        c.next = a[1]

    return comb


@block
def sac6(a, b):

    @always_comb
    def comb():
        b.next[1] = a[0]
        b.next[0] = a[1]

    return comb


@block
def sac7(a, b):

    @always_comb
    def comb():
        b.next[8:] = a[:8]
        b.next[:8] = a[8:]

    return comb


@block
def sac8(a, b, c, d , e):

    @always_comb
    def comb():
        e.next = not a and b and (c or d)

    return comb


@block
def sac9(a, b, c, d , e):

    @always_comb
    def comb():
        e.next = ~a & b & (c | d)

    return comb


@block
def sac10(aa, bb, cc):

    @always_comb
    def comb():
        cc.next[4:] = aa
        cc.next[:4] = bb

    return comb


@block
def sac11(a, b, c, d, e):

    @always_comb
    def comb():
        # ''' mixing 0,1 and True, False for Signal(bool()) '''

        d.next = False
        if a:
            d.next = e
        elif b and not c:
            d.next = not e
        elif not b and c:
            d.next = 1

    return comb


@block
def sac12(a, b, c, d, e):

    @always_comb
    def comb():
        ''' mixing 0,1 and True, False for Signal(bool()) '''

        ''' False '''
        d.next = False  # ''' False '''
        if a:
            d.next = e
        else:
            if b and not c:
                ''' 1 '''
                d.next = 1
            else:
                d.next = not e
        ''' Done '''

    return comb


@block
def sac13(a, b, c):

    @always_comb
    def comb():
        b.next = c
        if a:
            b.next = not c

    return comb


@block
def sac14(a, b):

    @always_comb
    def comb():
        if a == 0:
            b.next = 1
        elif a == 1:
            b.next = 2
        else:
            b.next = 0

    return comb


@block
def sac15(clk, a, b, c):
    ''' expecting 'new' VHDL 2008 q <= '0' when reset else d; '''

    @always_seq(clk.posedge, reset=None)
    def sync():
        b.next = not a if c else a

    return sync


@block
def simplecounter(RANGE, Clk, SClr, CntEn, Q):
    ''' a simple wrap-around counter '''

    MAX_COUNT = Constant(intbv(RANGE - 1)[6:])

    @always_seq(Clk.posedge, reset=None)
    def sc():
        ''' a simple counter '''
        if SClr or CntEn:
            if SClr:
                Q.next = 0
            elif Q == MAX_COUNT:
                Q.next = 0
            else:
                Q.next = Q + 1

    return instances()


@block
def scramble(Pattern, A, Y):
    NBR_BITS = len(Pattern)

    @always_comb
    def dsc():
        for i in range(NBR_BITS):
            if Pattern[i]:
                Y.next[i] = not A[i]
            else:
                Y.next[i] = A[i]

    return instances()


@block
def contrived(A, Y):
    WIDTH_D = len(A)
    PAT1 = Constant(intbv(0x42)[WIDTH_D:])
    PAT2 = Constant(intbv(0xbd)[WIDTH_D:])
    y1a2 = Signal(intbv(0)[WIDTH_D:])

    s1 = scramble(PAT1, A, y1a2)
    s2 = scramble(PAT2, y1a2, Y)

    return instances()


@block
def contrived2(A, Y):
    WIDTH_D = len(A)
    PAT = [Constant(intbv(0x42)[WIDTH_D:]), Constant(intbv(0xbd)[WIDTH_D:])]
    y1a2 = Signal(intbv(0)[WIDTH_D:])

    s1 = scramble(PAT[0], A, y1a2)
    s2 = scramble(PAT[1], y1a2, Y)

    return instances()


@block
def contrived3(WIDTH_D, Sel, Y):
    import random
    random.seed('We want repeatable randomness')

    A = [Constant(intbv(random.randint(1, 2 ** WIDTH_D - 1))[WIDTH_D:]) for __ in range(8)]

    @always_comb
    def cmux():
        Y.next = A[Sel]

    return instances()


@block
def contrived4(Clk, D, CE, Q):

    @always_seq(Clk.posedge, reset=None)
    def dff():
        if CE:
            Q.next = D

    return instances()


@block
def wrappercontrived4(Clk, D, Q):
    return contrived4(Clk, D, Constant(bool(1)), Q)


def test_contrived():
    WIDTH_D = 8
    A, Y = [Signal(intbv(0)[WIDTH_D:]) for __ in range(2)]
    assert contrived(A, Y).analyze_convert() == 0


def test_contrived2():
    WIDTH_D = 8
    A, Y = [Signal(intbv(0)[WIDTH_D:]) for __ in range(2)]
    assert contrived2(A, Y).analyze_convert() == 0


def test_contrived3():
    WIDTH_D = 8
    Y = Signal(intbv(0)[WIDTH_D:])
    Sel = Signal(intbv(0)[3:])
    assert contrived3(8, Sel, Y).analyze_convert() == 0


def test_contrived4():
    Clk, D , Q = [Signal(bool(0)) for __ in range(3)]
    CE = Signal(bool(0))
    assert contrived4(Clk, D, CE, Q).analyze_convert() == 0


def test_contrived4b():
    Clk, D , Q = [Signal(bool(0)) for __ in range(3)]
    assert wrappercontrived4(Clk, D, Q).analyze_convert() == 0


if __name__ == '__main__':

    from myhdl import delay, instance, StopSimulation

    @block
    def tb_contrived():
        WIDTH_D = 8
        A, Y = [Signal(intbv(0)[WIDTH_D:]) for __ in range(2)]

        # dut = contrived(A, Y)
        dut2 = contrived2(A, Y)

        @instance
        def stimulus():
            A.next = 0x42
            yield delay(10)
            A.next = Y
            yield delay(10)
            assert Y == 0x42

            raise StopSimulation

        return instances()

    def convert():
        clk = Signal(bool(0))
        A, B, C, D, E = [Signal(bool(0)) for __ in range(5)]
        AA = Signal(intbv()[2:])
        BB = Signal(intbv()[2:])
        AAA = Signal(intbv()[16:])
        BBB = Signal(intbv()[16:])
        Q = Signal(modbv(0, min=0, max=42)[6:])
        CC = Signal(intbv()[4:])
        DD = Signal(intbv()[4:])
        EE = Signal(intbv()[8:])
        # dfc = sac(A, B, C)
        # dfc = sac2(A, B, C, D, E)
        # dfc = sac3(AA, B)
        # dfc = sac4(AA, B)
        # dfc = sac5(AA, B, C)
        # dfc = sac6(AA, BB)
        # dfc = sac7(AAA, BBB)
        # dfc = sac8(A, B, C, D, E)
        # dfc = sac9(A, B, C, D, E)
        # dfc = sac10(CC, DD, EE)
        # dfc = simplecounter(42, A, B, C, Q)
        # dfc = sac11(A, B, C, D, E)
        # dfc = sac12(A, B, C, D, E)
        # dfc = sac13(A, B, C)
        # dfc = sac14(AA, BB)
        dfc = sac15(clk, A, B, C)
        # dfc.convert(hdl='Verilog')
        dfc.convert(hdl='VHDL')

        # WIDTH_D = 8
        #
        # A, Y = [Signal(intbv(0)[WIDTH_D:]) for __ in range(2)]
        # Sel = Signal(intbv(0)[3:])
        # Clk, D , Q = [Signal(bool(0)) for __ in range(3)]
        # CE = Signal(bool(0))

        # dfc = contrived(A, Y)
        # # dfc.convert(hdl='VHDL')
        # dfc.convert(hdl='Verilog')

        # dfc2 = contrived2(A, Y)
        # # dfc2.convert(hdl='VHDL')
        # dfc2.convert(hdl='Verilog')
        #
        # dfc3 = contrived3(WIDTH_D, Sel, Y)
        # # dfc3.convert(hdl='VHDL')
        # dfc3.convert(hdl='Verilog')
        #
        # dfc4 = contrived4(Clk, D, CE, Q)
        # # dfc4.convert(hdl='VHDL')
        # dfc4.convert(hdl='Verilog')
        #
        # dfc5 = wrappercontrived4(Clk, D, Q)
        # # dfc5.convert(hdl='VHDL', name='contrived4b')
        # dfc5.convert(hdl='Verilog', name='contrived4b')

    # dft = tb_contrived()
    # dft.config_sim(trace=True)
    # dft.run_sim()
    # print("Simulation passed")

    convert()


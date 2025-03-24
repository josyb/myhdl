import os
path = os.path

from myhdl import (block, Signal, intbv, delay, always_comb, always_seq,
                   always, instance, StopSimulation, conversion)


@block
def ternary1(dout, clk, rst):

    @always(clk.posedge, rst.negedge)
    def comb():
        if rst == 0:
            dout.next = 0
        else:
            dout.next = (dout + 1) if dout < 127 else 0

    return comb


@block
def ternary2(dout, clk, rst):

    dout_d = Signal(intbv(0)[len(dout):])

    @always(clk.posedge, rst.negedge)
    def synch():
        if rst == 0:
            dout.next = 0
        else:
            dout.next = dout_d

    @always_comb
    def comb():
        dout_d.next = (dout + 1) if dout < 127 else 0

    return synch, comb


@block
def ternary3(dout, clk, rst):

    def ndout(dout):
        if 1:
            return (dout + 1) if dout < 127 else 0
        else:
            v = intbv(0)[len(dout):]
            v[:] = (dout + 1) if dout < 127 else 0
            return v

    dout_d = Signal(intbv(0)[len(dout):])

    @always(clk.posedge, rst.negedge)
    def synch():
        if rst == 0:
            dout.next = 0
        else:
            dout.next = dout_d

    @always_comb
    def comb():
        # dout_d.next = (dout + 1) if dout < 127 else 0 if wrap else dout
        dout_d.next = ndout(dout)

    return synch, comb


@block
def ternary4(dout, wrap, clk, rst):

    def ndout(dout, wrap):
        return (dout + 1) if dout < 127 else (0 if wrap else dout)

    dout_d = Signal(intbv(0)[len(dout):])

    @always(clk.posedge, rst.negedge)
    def synch():
        if rst == 0:
            dout.next = 0
        else:
            dout.next = dout_d

    @always_comb
    def comb():
        dout_d.next = ndout(dout, wrap)

    return synch, comb


@block
def TernaryBench(ternary, name):

    dout = Signal(intbv(0)[8:])
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    ternary_inst = ternary(dout, clk, rst)
    ternary_inst.name = name

    @instance
    def stimulus():
        rst.next = 1
        clk.next = 0
        yield delay(10)
        rst.next = 0
        yield delay(10)
        rst.next = 1
        yield delay(10)
        for i in range(1000):
            clk.next = 1
            yield delay(10)
            assert dout == (i + 1) % 128
            print(dout)
            clk.next = 0
            yield delay(10)

        raise StopSimulation()

    return stimulus, ternary_inst


# uncomment when we have a VHDL-2008 compliant simulator
def test_ternary1():
    assert conversion.verify(TernaryBench(ternary1, 'ternary1')) == 0


def test_ternary2():
    assert conversion.verify(TernaryBench(ternary2, 'ternary2')) == 0

# def test_ternary3():
#     dout = Signal(intbv(0)[8:])
#     clk = Signal(bool(0))
#     rst = Signal(bool(0))
#
#     assert conversion.analyze(ternary3(dout, clk, rst)) == 0

# def test_ternary4():
#     dout = Signal(intbv(0)[8:])
#     wrap = Signal(bool(0))
#     clk = Signal(bool(0))
#     rst = Signal(bool(0))
#
#     assert conversion.analyze(ternary4(dout, wrap, clk, rst)) == 0


@block
def ternary5(Clk, A, B, Y):

    def sign(x):
        s = intbv(0, -1, 2)
        s[:] = -1 if x < 0 else (+1 if x > 0 else 0)
        return s

    @always_seq(Clk.posedge, reset=None)
    def synch():
        if sign(B):
            Y.next = A * B
        else:
            Y.next = 0

    return synch


def test_ternary5():
    Clk = Signal(bool(0))
    A = Signal(intbv(0, -256, 256))
    B = Signal(intbv(0, -256, 256))
    Y = Signal(intbv(0, -256 * 256, 256 * 256))

    assert conversion.analyze(ternary5(Clk, A, B, Y)) == 0


if __name__ == '__main__':
    pass
    # dout = Signal(intbv(0)[8:])
    # wrap = Signal(bool(0))
    # clk = Signal(bool(0))
    # rst = Signal(bool(0))
    #
    # assert conversion.analyze(ternary3(dout, clk, rst)) == 0

    #
    #
    # Clk = Signal(bool(0))
    # A = Signal(intbv(0, -256, 256))
    # B = Signal(intbv(0, -256, 256))
    # Y = Signal(intbv(0, -256 * 256, 256 * 256))
    # assert conversion.analyze(ternary5(Clk, A, B, Y)) == 0

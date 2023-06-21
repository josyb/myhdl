from myhdl import (block, Signal, intbv, always_comb,
                   instance, delay, StopSimulation,)


@block
def byteswap(A, Y):
    NBR_ELEMENTS = len(A)

    @always_comb
    def bs():
        for i in range(NBR_ELEMENTS):
            Y[i].next = A[NBR_ELEMENTS - 1 - i]

    return bs


@block
def c_testbench_one():
    A = [Signal(intbv(0)[8:]) for __ in range(4)]
    Y = [Signal(intbv(0)[8:]) for __ in range(4)]

    dut = byteswap(A, Y)

    @instance
    def tb_stim():
        A[0].next = 1
        A[1].next = 2
        A[2].next = 3
        A[3].next = 4

        yield delay(10)

        assert Y[0] == 4
        assert Y[1] == 3
        assert Y[2] == 2
        assert Y[3] == 1
        print('Success! A -> Y', A[0], Y[3])

        yield delay(10)

        raise StopSimulation

    return dut, tb_stim


def test_one_level_analyze():
    A = [Signal(intbv(0)[8:]) for __ in range(4)]
    Y = [Signal(intbv(0)[8:]) for __ in range(4)]
    inst = byteswap(A, Y)
    assert inst.analyze_convert() == 0


def test_one_level_verify():
    inst = c_testbench_one()
    assert inst.verify_convert() == 0


if __name__ == '__main__':

    A = [Signal(intbv(0)[8:]) for __ in range(4)]
    Y = [Signal(intbv(0)[8:]) for __ in range(4)]
    dfc = byteswap(A, Y)
    # dfc.convert(hdl='VHDL', std_logic_ports=True)
    dfc.convert(hdl='Verilog')


from myhdl import (block, Signal, intbv, always_comb,
                   instance, delay, StopSimulation,
                   ConcatSignal)

# @block
# def byteswap(A, Y):
#     NBR_ELEMENTS = len(A)
#
#     @always_comb
#     def bs():
#         for i in range(NBR_ELEMENTS):
#             Y[i].next = A[NBR_ELEMENTS - 1 - i]
#
#     return bs
#
#
# class bs(object):
#
#     def __init__(self):
#         self.A = [Signal(intbv(0)[8:]) for __ in range(4)]
#         self.Y = [Signal(intbv(0)[8:]) for __ in range(4)]
#
#
# @block
# def byteswap2(C):
#     NBR_ELEMENTS = len(C.A)
#
#     @always_comb
#     def bs():
#         for i in range(NBR_ELEMENTS):
#             C.Y[i].next = C.A[NBR_ELEMENTS - 1 - i]
#
#     return bs
#
#
# @block
# def c_testbench_one():
#     A = [Signal(intbv(0)[8:]) for __ in range(4)]
#     Y = [Signal(intbv(0)[8:]) for __ in range(4)]
#
#     dut = byteswap(A, Y)
#
#     @instance
#     def tb_stim():
#         A[0].next = 1
#         A[1].next = 2
#         A[2].next = 3
#         A[3].next = 4
#
#         yield delay(10)
#
#         assert Y[0] == 4
#         assert Y[1] == 3
#         assert Y[2] == 2
#         assert Y[3] == 1
#         print('Success! A -> Y', A[0], Y[3])
#
#         yield delay(10)
#
#         raise StopSimulation
#
#     return dut, tb_stim
#
#
# @block
# def tointbv(A, V):
#     ac = ConcatSignal(*reversed(A))
#
#     @always_comb
#     def ti():
#         V.next = ac
#
#     return ti


@block
def tointbva(A, V):
    NUM_ELEMENTS = len(A)
    WIDTH_ELEMENTS = len(A[0])
    ac = Signal(intbv(0)[NUM_ELEMENTS * WIDTH_ELEMENTS:])

    @always_comb
    def ti():
        for i in range(NUM_ELEMENTS):
            ac.next[i * WIDTH_ELEMENTS + WIDTH_ELEMENTS:i * WIDTH_ELEMENTS] = A[i]
        V.next = ac

    return ti

# class demo(object):
#
#     def __init__(self):
#         self.A = [Signal(intbv(0)[8:]) for __ in range(4)]
#         self.W = Signal(intbv(0)[32:])
#
#
# @block
# def tointbv2(C):
#     ac = ConcatSignal(*reversed(C.A))
#
#     @always_comb
#     def ti():
#         C.W.next = ac
#
#     return ti
#
#
# @block
# def c_testbench_three():
#     C = demo()
#
#     dut = tointbv2(C)
#
#     @instance
#     def tb_stim():
#         C.A[0].next = 1
#         C.A[1].next = 2
#         C.A[2].next = 3
#         C.A[3].next = 4
#
#         yield delay(10)
#
#         assert C.W == 0x04030201
#         print('Success! A -> W', C.A[0], C.W)
#
#         yield delay(10)
#
#         raise StopSimulation
#
#     return dut, tb_stim
#
#
# def test_byteswap_analyze():
#     A = [Signal(intbv(0)[8:]) for __ in range(4)]
#     Y = [Signal(intbv(0)[8:]) for __ in range(4)]
#     inst = byteswap(A, Y)
#     assert inst.analyze_convert() == 0
#
#
# def test_byteswap2_analyze():
#     C = bs()
#     inst = byteswap(C)
#     assert inst.analyze_convert() == 0
#
#
# def test_tointbv_analyze():
#     A = [Signal(intbv(0)[8:]) for __ in range(4)]
#     V = Signal(intbv(0)[8 * 4:])
#     inst = tointbv(A, V)
#     assert inst.analyze_convert() == 0
#
#
# def test_tointbv2_analyze():
#     C = demo()
#     inst = tointbv2(C)
#     assert inst.analyze_convert() == 0
#
#
# def test_byteswap_verify():
#     inst = c_testbench_one()
#     assert inst.verify_convert() == 0
#
#
# def test_tointbv2_verify():
#     inst = c_testbench_three()
#     assert inst.verify_convert() == 0


if __name__ == '__main__':

    # A1 = [Signal(intbv(0)[8:]) for __ in range(4)]
    # A2 = [Signal(intbv(0)[8:]) for __ in range(4)]
    A3 = [Signal(intbv(0)[8:]) for __ in range(4)]
    # Y = [Signal(intbv(0)[8:]) for __ in range(4)]
    V3 = Signal(intbv(0)[8 * 4:])
    # C = demo()
    # C2 = bs()

    # dfc = byteswap(A1, Y)
    # dfc.convert(hdl='Verilog')
    # dfc.convert(hdl='VHDL', name='byteswap_slv', std_logic_ports=True)
    # dfc.convert(hdl='VHDL')
    #
    # dfc2 = tointbv(A2, V)
    # dfc2.convert(hdl='Verilog')
    # dfc2.convert(hdl='VHDL')
    # dfc2.convert(hdl='VHDL', name='toinbtbv_slv', std_logic_ports=True)
    #
    dfc2a = tointbva(A3, V3)
    # dfc2a.convert(hdl='Verilog')
    dfc2a.convert(hdl='VHDL')
    # dfc2a.convert(hdl='VHDL', name='toinbtbva_slv', std_logic_ports=True)

    # dfc3 = tointbv2(C)
    # dfc3.convert(hdl='Verilog')
    # dfc3.convert(hdl='VHDL', name='toinbtbv2_slv', std_logic_ports=True)
    # dfc3.convert(hdl='VHDL')
    #
    # dfc4 = byteswap2(C2)
    # dfc4.convert(hdl='Verilog')
    # dfc4.convert(hdl='VHDL', name='byteswap2_slv', std_logic_ports=True)
    # dfc4.convert(hdl='VHDL')


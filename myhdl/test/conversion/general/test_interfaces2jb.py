
from myhdl import (block, Signal, ResetSignal, intbv, always_seq)


class Intf(object):

    def __init__(self):
        self.x = Signal(intbv(1, min=-1111, max=1111))
        self.y = Signal(intbv(2, min=-2211, max=2211))
        self.z = Signal(intbv(3, min=-3311, max=3311))


@block
def name_conflict_after_replace(clock, reset, a, a_x):
    a_x_0 = [Signal(intbv(0)[len(a_x):]) for _ in range(8)]

    @always_seq(clock.posedge, reset=reset)
    def logic():
        a.x.next = a_x
        a_x.next = a_x_0[1]

    return logic


def test_name_conflict_after_replace():
    clock = Signal(False)
    reset = ResetSignal(0, active=0, isasync=False)
    a = Intf()
    a_x = Signal(intbv(0)[len(a.x):])
    inst = name_conflict_after_replace(clock, reset, a, a_x)
    assert inst.analyze_convert() == 0


if __name__ == '__main__':

    @block
    def wrapper(clk, reset, ta, tb):
        tt = name_conflict_after_replace(clk, reset, ta, tb)

        return tt

    @block
    def wrapper2(clk=Signal(bool(0)), reset=ResetSignal(0, 1, True),
                 tta=Intf(), ttb=Signal(intbv(1, min=-1111, max=1111))):
        ttt = name_conflict_after_replace(clk, reset, tta, ttb)

        return ttt

    Clk = Signal(bool(0))
    Reset = ResetSignal(0, 1, True)
    ab = Intf()
    ab_x = Signal(intbv(0)[len(ab.x):])

    dfc = name_conflict_after_replace(Clk, Reset, ab, ab_x)
    dfc.convert('VHDL')

    dfc2 = wrapper(Signal(bool(0)), ResetSignal(0, 1, True),
                 Intf(), Signal(intbv(1, min=-1111, max=1111)))
    dfc2.convert('VHDL')

    dfc3 = wrapper2()
    dfc3.convert('VHDL')

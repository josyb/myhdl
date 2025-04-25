import os
path = os.path
# import unittest
from unittest import TestCase

from myhdl import (enum, block, Signal, intbv, always, instance, delay,
                   StopSimulation, getcosimkwargs, setupcosimobject, instances)

# from .util import setupCosimulation

# SEARCH, CONFIRM, SYNC = range(3)
ACTIVE_LOW = 0
FRAME_SIZE = 8
t_State_b = enum('SEARCH', 'CONFIRM', 'SYNC')
t_State_oh = enum('SEARCH', 'CONFIRM', 'SYNC', encoding="one_hot")
t_State_oc = enum('SEARCH', 'CONFIRM', 'SYNC', encoding="one_cold")


@block
def FramerCtrl(SOF, state, syncFlag, clk, reset_n, t_State):

    """ Framing control FSM.

    SOF -- start-of-frame output bit
    state -- FramerState output
    syncFlag -- sync pattern found indication input
    clk -- clock input
    reset_n -- active low reset

    """

    index = Signal(intbv(0)[8:])  # position in frame

    @always(clk.posedge, reset_n.negedge)
    def FSM():
        if reset_n == ACTIVE_LOW:
            SOF.next = 0
            index.next = 0
            state.next = t_State.SEARCH
        else:
            index.next = (index + 1) % FRAME_SIZE
            SOF.next = 0
            if state == t_State.SEARCH:
                index.next = 1
                if syncFlag:
                    state.next = t_State.CONFIRM
            elif state == t_State.CONFIRM:
                if index == 0:
                    if syncFlag:
                        state.next = t_State.SYNC
                    else:
                        state.next = t_State.SEARCH
            elif state == t_State.SYNC:
                if index == 0:
                    if not syncFlag:
                        state.next = t_State.SEARCH
                SOF.next = (index == FRAME_SIZE - 1)
            else:
                raise ValueError("Undefined state")

    return FSM


@block
def FramerCtrl_alt(SOF, state, syncFlag, clk, reset_n, t_State):

    """ Framing control FSM.

    SOF -- start-of-frame output bit
    state -- FramerState output
    syncFlag -- sync pattern found indication input
    clk -- clock input
    reset_n -- active low reset

    """

    @instance
    def FSM():
        index = intbv(0)[8:]  # position in frame
        state_var = t_State.SEARCH
        while 1:
            yield clk.posedge, reset_n.negedge
            if reset_n == ACTIVE_LOW:
                SOF.next = 0
                index[:] = 0
                state_var = t_State.SEARCH
                state.next = t_State.SEARCH
            else:
                SOF_var = 0
                if state == t_State.SEARCH:
                    index[:] = 0
                    if syncFlag:
                        state_var = t_State.CONFIRM
                elif state == t_State.CONFIRM:
                    if index == 0:
                        if syncFlag:
                            state_var = t_State.SYNC
                        else:
                            state_var = t_State.SEARCH
                elif state == t_State.SYNC:
                    if index == 0:
                        if not syncFlag:
                            state_var = t_State.SEARCH
                    SOF_var = (index == FRAME_SIZE - 1)
                else:
                    raise ValueError("Undefined state")
                index[:] = (index + 1) % FRAME_SIZE
                SOF.next = SOF_var
                state.next = state_var

    return FSM


@block
def FramerCtrl_ref(SOF, state, syncFlag, clk, reset_n, t_State):

    """ Framing control FSM.

    SOF -- start-of-frame output bit
    state -- FramerState output
    syncFlag -- sync pattern found indication input
    clk -- clock input
    reset_n -- active low reset

    """

    # index = Signal(intbv(0, min=0, max=8))  # position in frame

    @instance
    def fsm_ref():
        index = intbv(0, min=0, max=8)  # position in frame

        while 1:
            yield clk.posedge, reset_n.negedge

            if reset_n == ACTIVE_LOW:
                SOF.next = 0
                index[:] = 0
                # index.next = 0
                state.next = t_State.SEARCH

            else:
                SOF.next = 0
                if state == t_State.SEARCH:
                    index[:] = 0
                    # index.next = 0
                    if syncFlag:
                        state.next = t_State.CONFIRM

                elif state == t_State.CONFIRM:
                    if index == 0:
                        if syncFlag:
                            state.next = t_State.SYNC
                        else:
                            state.next = t_State.SEARCH

                elif state == t_State.SYNC:
                    if index == 0:
                        if not syncFlag:
                            state.next = t_State.SEARCH
                        # else:
                        #     index.next = (index + 1) % FRAME_SIZE
                    SOF.next = (index == FRAME_SIZE - 1)

                else:
                    raise ValueError("Undefined state")

                index[:] = (index + 1) % FRAME_SIZE

    return fsm_ref

# @block
# def FramerCtrl_v(name, SOF, state, syncFlag, clk, reset_n):
#     return setupCosimulation(**locals())


class FramerCtrlTest(TestCase):

    @block
    def bench(self, FramerCtrl, t_State):

        SOF = Signal(bool(0))
        syncFlag = Signal(bool(0))
        clk = Signal(bool(0))
        reset_n = Signal(bool(1))
        state = Signal(t_State.SEARCH)

        framerctrl_inst = FramerCtrl(SOF, state, syncFlag, clk, reset_n, t_State).convert(hdl='SystemVerilog', trace=True)
        cosimkwargs = getcosimkwargs('FramerCtrlTest', hdl='SystemVerilog', simulator='sverilog',
                                     inst=framerctrl_inst, localsdict=locals())
        # and create the Cosimulator object
        cosimobj = setupcosimobject(**cosimkwargs)

        SOFcosim = cosimkwargs['SOF']
        statecosim = cosimkwargs['state']

        tCK = 10

        @instance
        def clkgen():
            reset_n.next = 1
            yield delay(tCK)
            reset_n.next = 0
            yield delay(tCK)
            reset_n.next = 1
            yield delay(tCK)
            while 1:
                yield delay(tCK)
                clk.next = not clk

        @instance
        def stimulus():
            for dummy in range(3):
                yield clk.posedge
            for n in (12, 8, 8, 4, 11, 8, 8, 7, 6, 8, 8):
                yield delay(tCK // 4)
                syncFlag.next = 1
                yield clk.posedge
                yield delay(tCK // 4)
                syncFlag.next = 0
                for dummy in range(n - 1):
                    yield clk.posedge
            raise StopSimulation

        @instance
        def check():
            while 1:
                yield clk.negedge
                print("MyHDL:         %s %s" % (SOF, hex(state)))
                print("SystemVerilog: %s %s" % (SOFcosim, hex(statecosim)))
                # self.assertEqual(SOF, SOF_v)
                if SOF != SOFcosim:
                    raise AssertionError(f'{SOF=} != {SOFcosim=}?')
                if state != statecosim:
                    raise AssertionError(f'{state=} != {statecosim=}?')
                # self.assertEqual(eval(hex(state)), eval(hex(state_v)))

        return instances()

    def testRef(self):
        for t_State in (t_State_b, t_State_oc, t_State_oh):
            tb_fsm = self.bench(FramerCtrl_ref, t_State)
            tb_fsm.run_sim()

    def testAlt(self):
        for t_State in (t_State_b, t_State_oc, t_State_oh):
            tb_fsm = self.bench(FramerCtrl_alt, t_State)
            tb_fsm.run_sim()

    def testDoc(self):
        tb_fsm = self.bench(FramerCtrl, t_State_oh)
        tb_fsm.run_sim()

    # def testOne(self):
    #     tb_fsm = self.bench(FramerCtrl_alt, t_State_b)
    #     tb_fsm.config_sim(trace=True, tracebackup=False, name='tb_testOne')
    #     tb_fsm.run_sim()


if __name__ == '__main__':
    # unittest.main()
    FramerCtrlTest().testOne()


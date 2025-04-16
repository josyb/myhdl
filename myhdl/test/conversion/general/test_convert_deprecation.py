from myhdl import (Signal, intbv, always_comb, conversion, toVHDL, toVerilog)
from myhdl._Simulation import Simulation
from myhdl._traceSignals import traceSignals

import pytest

# !!! NO @block here, we are testing the 'old style' conversion


def bin2gray_depr(B, G, width):

    """ Gray encoder.

    B -- input intbv signal, binary encoded
    G -- output intbv signal, gray encoded
    width -- bit width

    """

    Bext = intbv(0)[width + 1:]

    @always_comb
    def comb():
        Bext[:] = B
        for i in range(width):
            G.next[i] = Bext[i + 1] ^ Bext[i]

    return comb


width = 1
BB = Signal(intbv(0)[width:])
GG = Signal(intbv(0)[width:])


def testOldVerify():
    with pytest.deprecated_call():
        conversion.verify(bin2gray_depr, BB, GG, width)


def testOldAnalyze():
    with pytest.deprecated_call():
        conversion.analyze(bin2gray_depr, BB, GG, width)


def testOldToVHDL():
    with pytest.deprecated_call():
        toVHDL(bin2gray_depr, BB, GG, width)


def testOldToVerilog():
    with pytest.deprecated_call():
        toVerilog(bin2gray_depr, BB, GG, width)


def testOldToTraceSignals():
    with pytest.deprecated_call():
        vcd = traceSignals(bin2gray_depr, width, BB, GG)
        sim = Simulation(vcd)
        sim.run(20)


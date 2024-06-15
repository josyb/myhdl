import os

from tempfile import mkdtemp
from shutil import rmtree

from myhdl import (block, Signal, intbv, always)

# from myhdl import __version__
# _version = __version__.replace('.', '')
# _shortversion = _version.replace('dev', '')[:-2]


@block
def simple_dir_model(din, dout, clk):
    """ Simple convertible model """

    @always(clk.posedge)
    def register():
            dout.next = din

    return register


def test_toVHDL_set_dir():
    '''In order that a developer can define where in the project 
    hierarchy any generated VHDL files should be placed, it should be 
    possible to set a directory attribute on toVHDL controlling this.
    '''

    tmp_dir = mkdtemp()

    din = Signal(intbv(0)[5:])
    dout = Signal(intbv(0)[5:])
    clock = Signal(bool(0))

    try:
        dfc = simple_dir_model(din, dout, clock)
        dfc.convert('VHDL', directory=tmp_dir)
        assert os.path.exists(os.path.join(tmp_dir, 'simple_dir_model.vhd'))
        assert os.path.exists(os.path.join(tmp_dir, "pck_myhdl.vhd"))

    finally:
        rmtree(tmp_dir)


def test_toVerilog_set_dir():
    '''In order that a developer can define where in the project 
    hierarchy any generated Verilog files should be placed, it should be 
    possible to set a directory attribute on toVerilog controlling this.
    '''

    tmp_dir = mkdtemp()

    din = Signal(intbv(0)[5:])
    dout = Signal(intbv(0)[5:])
    clock = Signal(bool(0))

    try:
        dfc = simple_dir_model(din, dout, clock)
        dfc.convert('Verilog', directory=tmp_dir, testbench=False)

        assert os.path.exists(os.path.join(tmp_dir, 'simple_dir_model.v'))

    finally:
        rmtree(tmp_dir)


def test_toVerilog_testbench_set_dir():
    '''In order that generated Verilog test bench files are located in the 
    same place as the Verilog files, when the directory attribute of 
    toVerilog is set, this location should be used for the generated test
    bench files.
    '''

    tmp_dir = mkdtemp()

    din = Signal(intbv(0)[5:])
    dout = Signal(intbv(0)[5:])
    clock = Signal(bool(0))

    try:
        dfc = simple_dir_model(din, dout, clock)
        dfc.convert('Verilog', directory=tmp_dir)
        assert os.path.exists(os.path.join(tmp_dir, 'tb_simple_dir_model.v'))

    finally:
        rmtree(tmp_dir)

import os, sys
path = os.path
import subprocess
from glob import glob
from myhdl import Cosimulation


# Icarus
def setupCosimulationIcarus(**kwargs):
    name = kwargs['name']
    objfile = "%s.o" % name
    if path.exists(objfile):
        os.remove(objfile)
    analyze_cmd = ['iverilog', '-g2012', '-o', objfile, '%s.sv' % name, 'tb_%s.sv' % name]
    subprocess.call(analyze_cmd)
    vpifile = "myhdl"
    if sys.platform == "win32":
        # vpifiles = glob("myhdl.vpi", root_dir="C:\\", recursive=True)
        # TODO: shortcut to get things moving ...
        vpifiles = ["C:\\Programs\\iverilog\\lib\\ivl\\myhdl.vpi"]
    else:
        vpifiles = glob("**/myhdl.vpi", recursive=True)
    print(f'{vpifiles=}', file=sys.stderr)

    if 1 == len(vpifiles):
        vpifile = vpifiles[0]
    elif sys.platform != "win32":
        vpifile = "../../../../cosimulation/icarus/myhdl.vpi"
    simulate_cmd = ['vvp', '-m', vpifile, objfile]
    return Cosimulation(simulate_cmd, **kwargs)


# cver
def setupCosimulationCver(**kwargs):
    name = kwargs['name']
    cmd = "cver -q +loadvpi=../../../../cosimulation/cver/myhdl_vpi:vpi_compat_bootstrap " + \
          "%s.v tb_%s.v " % (name, name)
    return Cosimulation(cmd, **kwargs)


def verilogCompileIcarus(name):
    objfile = "%s.o" % name
    if path.exists(objfile):
        os.remove(objfile)
    analyze_cmd = "iverilog -g2012 -o %s %s.sv tb_%s.sv" % (objfile, name, name)
    os.system(analyze_cmd)


def verilogCompileCver(name):
    cmd = "cver -c %s.v" % name
    os.system(cmd)


setupCosimulation = setupCosimulationIcarus
# setupCosimulation = setupCosimulationCver

verilogCompile = verilogCompileIcarus
# verilogCompile = verilogCompileCver

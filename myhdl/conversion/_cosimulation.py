'''
Created on 27 mrt. 2025

@author: josy

    generic cosimulation helpers
'''

import os
import sys
import subprocess
from glob import glob

from myhdl import Cosimulation


def getfiles(design, ext):
    # TODO: the required files depend on the simulator ...
    # *icarus verilog* requires the full list, **and** in the correct order!
    # whereas *verilator* seems to be happy with just the top-level file and searches for the rest
    # TODO:   VHDL and SystemVerilog may have packages to be added
    # VHDL always has `pck_mhdl_xxx.vhd`, additionally there may be a `<project>_pkg.vhd`
    # SystemVerilog may have `myhdl_pkg.sv` (must come first) and a `<project>_pkg.sv`

    # so we return the top level together with the list

    name = design.name

    modules = []
    # first add any packages
    # each package entry carries the (relative?) path
    if hasattr(design, 'needsyspck'):
        # don't know where it resides, so look everywhere?
        modules.append(glob(f"**/myhdl_pkg.{ext}", recursive=True)[0])

    if hasattr(design, 'needprojectpck'):
        # must be in the same directory as the MyHDL top module
        modules.append(f'{design.name}_pkg.{ext}')

    if hasattr(design, 'modules'):
        # hierarchical != 0
        # then the converted modules
        # reside in a subdirectory of the MyHDL top module
        modules.extend([''.join((f'{name}/', m, '.', ext)) for m in design.modules])
        # and finally add the testbench (at the end) which
        # also resides along the MyHDL top module
        modules.append(f'tb_{name}_cosim.{ext}')
        top = f'{name}/{design.modules[0]}.{ext}'

    else:
        # we only have the flattened conversion, possibly some package(s) and the associated HDL test-bench
        top = f'{name}.{ext}'
        modules.extend([top, f'tb_{name}_cosim.{ext}'])

    return modules, top


def getcosimkwargs(name, hdl, simulator, inst, localsdict):
    # instead of requiring to have the locals() (in `localsdict`) passed to us
    # we could have used inspect and frames etc to find those
    # but passing them is simpler ...
    # TODO: use inspect anyway!

    ext = {'VHDL': 'vhd', 'Verilog': 'v', 'SystemVerilog': 'sv'}[hdl]
    files, top = getfiles(inst, ext)
    cosimkwargs = {'files': files,
                   'top': top,
                   'name': name,
                   'hdl': hdl,
                   'simulator': simulator,
                   }

    for arg in inst.argnames:
        if arg not in cosimkwargs:
            s = inst.argdict[arg]
            if s._used:
                if s._driven or s._driver:
                    # create a new receiver signal
                    # TODO: ListOfSignals for VHDL and SystemVerilog
                    ss = s.duplicate()
                    tname = f'{arg}cosim'
                    # print(tname)
                    localsdict[tname] = ss
                    cosimkwargs[arg] = ss
                else:
                    # input: just use orig signal
                    cosimkwargs[arg] = s

    return cosimkwargs


def setupcosimobject(**cosimkwargs):
    simulator = cosimkwargs.pop('simulator')
    files = cosimkwargs.pop('files')
    hdl = cosimkwargs.pop('hdl')
    name = cosimkwargs['name']

    # TODO: refactor code to get these from the specified simulator
    if simulator in ['iverilog', 'sverilog']:
        # Icarus Verilog Simulator
        # https://steveicarus.github.io/iverilog/

        objfile = f'{name}.o'
        if os.path.exists(objfile):
            os.remove(objfile)

        # we will make a command file, there may be a lot of modules
        # and we don't want to overflow the command line
        with open(f'{name}.icf', 'w') as f:
            f.write(f'# iverilog command file: {name}.icf\n\n')
            for file in files:
                f.write(f'{file}\n')

        compile_flags = '-g2012' if hdl == 'SystemVerilog' else '-g2005'
        compile_cmd = f'iverilog {compile_flags} -o {name}.o -c {name}.icf'
        # compile!
        subprocess.call(compile_cmd)
        vpifile = "myhdl"
        if sys.platform == "win32":
            # this will work everywhere, on every Win 10/11 machine :)
            vpifiles = glob("**/win32/icarus-myhdl.vpi", root_dir='\\')
        else:
            vpifiles = glob("**/myhdl.vpi", recursive=True)

        if 1 == len(vpifiles):
            vpifile = f'/{vpifiles[0]}'
        elif sys.platform != "win32":
            # TODO: not sure about Linux :(
            vpifile = "../../../../cosimulation/icarus/myhdl.vpi"

        simulate_cmd = ['vvp', '-m', vpifile, objfile]

    elif simulator == 'ghdl':
        compile_flags = '--std08'
        pass

    elif simulator == 'verilator':
        pass

    elif simulator == '...':
        pass

    else:
        pass

    # create a MyHDL Cosimulation object
    return Cosimulation(simulate_cmd, **cosimkwargs)


if __name__ == '__main__':
    pass

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
    name = design.name
    if hasattr(design, 'modules'):
        # hierarchical != 0
        svmodules = [''.join((f'{name}/', m, '.', ext)) for m in design.modules]
        # need to add the testbench (at the end)
        svmodules.append(f'tb_{name}_cosim.{ext}')
        return svmodules
    else:
        # we only have the flattened conversion and the associated HDL test-bench
        return [f'{name}.{ext}', f'tb_{name}_cosim.{ext}']


def getcosimkwargs(name, hdl, simulator, inst, localsdict):
    # instead of requiring to have the locals() (in `localsdict`) passed to us
    # we could have used inspect and frames etc to find those
    # but passing them is simpler ...
    # TODO: use inspect anyway!
    ext = {'VHDL': 'vhd', 'Verilog': 'v', 'SystemVerilog': 'sv'}[hdl]
    files = getfiles(inst, ext)
    cosimkwargs = {'files': files,
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

    objfile = f'{name}.o'
    if os.path.exists(objfile):
        os.remove(objfile)

    # TODO: refactor code to get these from the specified simulator
    if simulator in ['iverilog', 'sverilog']:
        compile_flags = '-g2012' if hdl == 'SystemVerilog' else '-g2005'
        # Icarus Verilog Simulator
        # https://steveicarus.github.io/iverilog/
        # we will make a command file, there may be a lot
        # and we don't want to overflow the command line
        with open(f'{name}.icf', 'w') as f:
            f.write(f'# iverilog command file: {name}.icf\n\n')
            for file in files:
                f.write(f'{file}\n')

        compile_cmd = f'iverilog {compile_flags} -o {name}.o -c {name}.icf'
        # compile!
        subprocess.call(compile_cmd)
        vpifile = "myhdl"
        if sys.platform == "win32":
            # this will work everywhere, on every Win 10/11 machine :)
            vpifiles = glob("**/win32/icarus-myhdl.vpi", root_dir='\\')
        else:
            vpifiles = glob("**/myhdl.vpi", recursive=True)
        print(vpifiles)
        if 1 == len(vpifiles):
            vpifile = f'/{vpifiles[0]}'
        elif sys.platform != "win32":
            vpifile = "../../../../cosimulation/icarus/myhdl.vpi"

        simulate_cmd = ['vvp', '-m', vpifile, objfile]

    elif simulator == 'ghdl':
        compile_flags = '--std08'
        pass

    elif simulator == '...':
        pass

    else:
        pass

    return Cosimulation(simulate_cmd, **cosimkwargs)


if __name__ == '__main__':
    pass

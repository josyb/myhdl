#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2015 Jan Decaluwe
#
#  The myhdl library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public License as
#  published by the Free Software Foundation; either version 2.1 of the
#  License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
#  Support for multiple entities (c) Jose M. Gomez

'''
Created on 2 jan. 2025

@author: josy

'''
# from collections import namedtuple
from types import GeneratorType

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl import  ConversionError
from myhdl._instance import _Instantiator
from myhdl._block import _Block
# from myhdl._extractHierarchy import  _userCodeMap, _UserCode, _isMem, _getMemInfo
from myhdl._extractHierarchy import  _UserCode, _isMem, _getMemInfo
from myhdl._Signal import _Signal
from myhdl._util import _flatten
from myhdl.conversion._misc import _error

# LevelInfo = namedtuple('LevelInfo', ['modulename', 'instancename', 'blocksubs' , 'gens'])


class LevelInfo(object):

    def __init__(self, modulename, instancename, blocksubs , gens):
        self.modulename = modulename
        self.instancename = instancename
        self.blocksubs = blocksubs
        self.gens = gens


def _checkArgs(arglist):
    for arg in arglist:
        if not isinstance(arg, (GeneratorType, _Instantiator, _UserCode)):
            raise ConversionError(_error.ArgType, arg)


def _flattenhierarchy(hdl, *args):
    # ic((args))
    arglist = []
    for arg in args:
        if isinstance(arg, _Block):
            if hdl in ('Verilog', 'SystemVerilog'):
                if arg.verilog_code is not None:
                    arglist.append(arg.verilog_code)
                    continue
                else:
                    arg = arg.subs

            elif hdl == 'VHDL':
                if arg.vhdl_code is not None:
                    arglist.append(arg.vhdl_code)
                    continue
                else:
                    arg = arg.subs

        # no `elif` as we now build the arglistg ...
        if isinstance(arg, (list, tuple, set)):
            for item in arg:
                arglist.extend(_flattenhierarchy(hdl, item))

        else:
            arglist.append(arg)

    # ic(arglist)

    return arglist


def collectsubs(top, hdl, level=0, maxdepth=-1, name_prefixes=[], hierarchy=[]):
    # ic(level, maxdepth, top, name_prefixes, hierarchy)
    if isinstance(top, _Block):
        # ic(level, top.name, name_prefixes, top.subs, top.symdict, top.sigdict, top.memdict)
        sigdictinfo = []
        for k, v in top.sigdict.items():
            sigdictinfo.append([k, v._info])
        # ic(sigdictinfo)

        if len(hierarchy) < level + 1:
            # start the first or new level
            hierarchy.append([])

        if maxdepth == -1:
            if top.endhierarchy:
                # walk down
                gens = _flattenhierarchy(hdl, top.subs)
            else:
                # only local generators
                gens = [ss for ss in top.subs if not isinstance(ss, _Block)]
        else:
            # > 0!
            if level == maxdepth:
                # walk down
                gens = _flattenhierarchy(hdl, top.subs)
            else:
                # only local generators
                gens = [ss for ss in top.subs if not isinstance(ss, _Block)]

        # sanity check
        _checkArgs(gens)
        # now append
        hierarchy[level].append(LevelInfo(top.name, '_'.join(name_prefixes) if level > 0 else top.name, top, gens))
        # this results in shorter module names, but still always unique?
        # TODO: re-visit this code?
        # hierarchy[level].append(LevelInfo(top.name, top.name, top, gens))

        if not top.endhierarchy and level != maxdepth:
            collectsubs(top.subs, hdl, level, maxdepth, name_prefixes, hierarchy)

    elif isinstance(top, (list, tuple, set)):
        for sub in top:
            name_prefixes.append(sub.name)
            collectsubs(sub, hdl, level + 1, maxdepth, name_prefixes, hierarchy)
            name_prefixes.pop(-1)

    else:
        pass


def gethierarchicalmodulenames(hierarchy):
    fl = []
    for level in hierarchy:
        fl.extend(level)
    # ic(fl)
    return [item.instancename for item in fl]


class _HierarchicalPort(object):

    def __init__(self, obj):
        self.obj = obj
        self._used = obj._used
        self._driven = obj._driven
        self._driver = obj._driver
        self._read = obj._read

    def __repr__(self):
        return f"_HierarchicalPort({repr(self.obj)}"

    @property
    def _info(self):
        return f'{repr(self)} used {self._used}, driven {self._driven}, driver {self._driver}, read {self._read} '


class _HierarchicalInstance(object):
    # __slots__ = ['hdlwriter', 'name', 'namespace', 'funcname', 'func', 'sourcefile', 'sourceline']

    # def __init__(self, hdlwriter, code, namespace, funcname, func, sourcefile, sourceline):
    def __init__(self, hdlwriter, name, argnames, argsigs, argports):
        # ic(name, argnames, argsigs)
        self.hdlwriter = hdlwriter
        self.name = name
        self.argnames = argnames
        self.sigdict = argsigs
        self.argports = argports
        # self.sourcefile = sourcefile
        # self.func = func
        # self.funcname = funcname
        # self.sourceline = sourceline

    def __str__(self):
        return self.hdlwriter.hierarchicalinstance(self)

    def __repr__(self):
        siginfo = []
        for sig in self.sigdict:
            if isinstance(sig, _Signal):
                siginfo.append(sig._info)
            elif _isMem(sig):
                m = _getMemInfo(sig)
                siginfo.append(m._info)

        return f"{self.name}, {self.argnames} -> {siginfo}"

#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2008 Jan Decaluwe
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

""" myhdl _extractHierarchy module.

"""
import sys
import inspect
import string

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl import ToVerilogError, ToVHDLError
from myhdl._Signal import _Signal

_profileFunc = None


class _error:
    pass


_error.NoInstances = "No instances found"
_error.InconsistentHierarchy = "Inconsistent hierarchy - are all instances returned ?"
_error.InconsistentToplevel = "Inconsistent top level %s for %s - should be 1"


class _Instance(object):
    __slots__ = ['level', 'obj', 'subs', 'sigdict', 'memdict', 'name']

    def __init__(self, level, obj, subs, sigdict, memdict):
        self.level = level
        self.obj = obj
        self.subs = subs
        self.sigdict = sigdict
        self.memdict = memdict
        self.name = None


_memInfoMap = {}


class _MemInfo(object):
    __slots__ = ['mem', 'name', 'elObj', 'depth', '_used', '_driven', '_read', '_readers']

    def __init__(self, mem):
        self.mem = mem
        self.name = None
        self.depth = len(mem)
        self.elObj = mem[0]
        self._used = False
        self._driven = None
        self._read = None
        self._readers = []

    def __repr__(self):
        if self.name:
            return f'{self.name} = _MemInfo({repr(self.mem)})'
        else:
            return f"Signal({repr(self.mem)})"

    @property
    def _info(self):
        return f'{repr(self)} used {self._used}, driven {self._driven}, read {self._read} '


def _getMemInfo(mem):
    return _memInfoMap[id(mem)]


def _makeMemInfo(mem):
    key = id(mem)
    if key not in _memInfoMap:
        _memInfoMap[key] = _MemInfo(mem)
    return _memInfoMap[key]


def _isMem(mem):
    return id(mem) in _memInfoMap

# TODO: check if _userCodeMap is still of any use?
# _userCodeMap = {'Verilog': {},
#                 'VHDL': {}
#                 }


class _UserCode(object):
    __slots__ = ['code', 'namespace', 'funcname', 'func', 'sourcefile', 'sourceline']

    def __init__(self, code, namespace, funcname, func, sourcefile, sourceline):
        self.code = code
        self.namespace = namespace
        self.sourcefile = sourcefile
        self.func = func
        self.funcname = funcname
        self.sourceline = sourceline
        ic((namespace))

    def __str__(self):
        try:
            code = self._interpolate()
        except:
            exctype, value, __ = sys.exc_info()
            info = "in file %s, function %s starting on line %s:\n    " % \
                   (self.sourcefile, self.funcname, self.sourceline)
            msg = "%s: %s" % (exctype, value)
            self.raiseError(msg, info)
        code = "\n%s\n" % code
        return code

    def _scrub_namespace(self):
        # ic((self.namespace))
        for nm, obj in self.namespace.items():
            if _isMem(obj):
                memi = _getMemInfo(obj)
                self.namespace[nm] = memi.name

    def _interpolate(self):
        self._scrub_namespace()
        return string.Template(self.code).substitute(self.namespace)


class _UserCodeDepr(_UserCode):

    def _interpolate(self):
        return self.code % self.namespace


class _UserVerilogCode(_UserCode):

    def raiseError(self, msg, info):
        raise ToVerilogError("Error in user defined Verilog code", msg, info)


class _UserVhdlCode(_UserCode):

    def raiseError(self, msg, info):
        raise ToVHDLError("Error in user defined VHDL code", msg, info)


class _UserVerilogCodeDepr(_UserVerilogCode, _UserCodeDepr):
    pass


class _UserVhdlCodeDepr(_UserVhdlCode, _UserCodeDepr):
    pass


class _UserVerilogInstance(_UserVerilogCode):

    def __str__(self):
        args = inspect.getfullargspec(self.func)[0]
        s = "%s %s(" % (self.funcname, self.code)
        sep = ''
        for arg in args:
            if arg in self.namespace and isinstance(self.namespace[arg], _Signal):
                signame = self.namespace[arg]._name
                s += sep
                sep = ','
                s += "\n    .%s(%s)" % (arg, signame)
        s += "\n);\n\n"
        return s


class _UserVhdlInstance(_UserVhdlCode):

    def __str__(self):
        args = inspect.getfullargspec(self.func)[0]
        s = "%s: entity work.%s(MyHDL)\n" % (self.code, self.funcname)
        s += "    port map ("
        sep = ''
        for arg in args:
            if arg in self.namespace and isinstance(self.namespace[arg], _Signal):
                signame = self.namespace[arg]._name
                s += sep
                sep = ','
                s += "\n        %s=>%s" % (arg, signame)
        s += "\n    );\n\n"
        return s


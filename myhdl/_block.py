#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2016 Jan Decaluwe
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

#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

""" Block with the @block decorator function. """
import os
import inspect

# from functools import wraps
import functools

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

import myhdl
from myhdl import BlockError, Cosimulation
from myhdl._instance import _Instantiator
from myhdl._util import _flatten
from myhdl._extractHierarchy import (_makeMemInfo,
                                     _UserVerilogCode, _UserVhdlCode,
                                     _UserVerilogInstance, _UserVhdlInstance)
from myhdl._Signal import _Signal, _isListOfSigs
from myhdl._misc import isboundmethod, updatesymdict, getsymdict
from myhdl._hdlclass import HdlClass

from weakref import WeakValueDictionary


class _error:
    pass


_error.ArgType = "%s: A block should return block or instantiator objects"
_error.InstanceError = "%s: subblock %s should be encapsulated in a block decorator"


class _CallInfo(object):

    def __init__(self, name, modctxt, symdict, filename):
        self.name = name
        self.modctxt = modctxt
        self.symdict = symdict
        self.filename = filename


def _getCallInfo(hdlclass):
    """Get info on the caller of a BlockInstance.

    A BlockInstance should be used in a block context.
    This function gets the required info from the caller
    It uses the frame stack:
    0: this function
    1: block instance constructor
    2: the decorator function call
    if hdlcass is None:
        3: the function that defines instances
        4: the caller of the block function, e.g. a BlockInstance.
    else:
        3: ?
        4: the function that defines instances
        5: ? the caller of the block function, e.g. ... ?

    """

    if hdlclass is not None:
        FUNCREC = 4
    else:
        FUNCREC = 3

    stack = inspect.stack()
    # ic(hdlclass, stack)
    # for i, f in enumerate(stack):
    #     ic(i, f[0].f_globals, f[0].f_locals)

    # caller may be undefined if instantiation from a Python module
    callerrec = None
    funcrec = stack[FUNCREC]
    name = funcrec[FUNCREC]
    if len(stack) > (FUNCREC + 1):
        callerrec = stack[FUNCREC + 1]
    # special case for list comprehension's extra scope in PY3
    if name == '<listcomp>':
        funcrec = stack[FUNCREC + 2]
        if len(stack) > 5:
            callerrec = stack[5]

    name = funcrec[FUNCREC]  # redo as the <listcomp> may have disturbed us
    frame = funcrec[0]
    filename = funcrec[1]
    # symdict = dict(frame.f_globals)
    # symdict.update(frame.f_locals)
    symdict = getsymdict(frame.f_globals)
    updatesymdict(symdict, frame.f_locals)
    # ic(symdict)
    modctxt = False
    if callerrec is not None:
        f_locals = callerrec[0].f_locals
        # ic(f_locals)
        if 'self' in f_locals:
            modctxt = isinstance(f_locals['self'], _Block)

    return _CallInfo(name, modctxt, symdict, filename)


# ## I don't think this is the right place for uniqueifying the name.
# ## This seems to me to be a conversion concern, not a block concern, and
# ## there should not be the corresponding global state to be maintained here.
# ## The name should be whatever it is, which is then uniqueified at
# ## conversion time. Perhaps this happens already (FIXME - check and fix)
# ## ~ H Gomersall 24/11/2017
_inst_name_set = set()
_name_set = set()


def _uniqueify_name(proposed_name):
    '''
        Creates a unique block name from the proposed name by appending
        a suitable number to the end. Every name this function returns is
        assumed to be used, so will not be returned again.
    '''
    n = 0

    while proposed_name in _name_set:
        proposed_name = proposed_name + '_' + str(n)
        n += 1

    _name_set.add(proposed_name)

    return proposed_name


class _bound_function_wrapper(object):

    def __init__(self, bound_func, srcfile, srcline):
        self.srcfile = srcfile
        self.srcline = srcline
        self.bound_func = bound_func
        functools.update_wrapper(self, bound_func)
        self.calls = 0
        # register the block
        myhdl._simulator._blocks.append(self)

        self.name_prefix = None
        self.name = None

    def __call__(self, *args, **kwargs):
        # name = self.name_prefix + '_' + self.bound_func.__name__ +  str(self.calls)
        name = f'{self.name_prefix}_{self.bound_func.__name__}{self.calls}'
        self.calls += 1
        # See concerns above about uniqueifying
        name = _uniqueify_name(name)

        return _Block(self.bound_func, self, name, self.srcfile,
                      self.srcline, *args, **kwargs)


class block(object):

    def __init__(self, func):
        self.srcfile = inspect.getsourcefile(func)
        self.srcline = inspect.getsourcelines(func)[0]
        self.func = func
        functools.update_wrapper(self, func)
        self.calls = 0
        self.name = None

        # register the block
        myhdl._simulator._blocks.append(self)

        self.bound_functions = WeakValueDictionary()

    def __get__(self, instance, owner):
        bound_key = (id(instance), id(owner))

        if bound_key not in self.bound_functions:
            bound_func = self.func.__get__(instance, owner)
            function_wrapper = _bound_function_wrapper(
                bound_func, self.srcfile, self.srcline)
            self.bound_functions[bound_key] = function_wrapper

            proposed_inst_name = owner.__name__ + '0'

            n = 1
            while proposed_inst_name in _inst_name_set:
                proposed_inst_name = owner.__name__ + str(n)
                n += 1

            function_wrapper.name_prefix = proposed_inst_name
            _inst_name_set.add(proposed_inst_name)

        else:
            function_wrapper = self.bound_functions[bound_key]
            bound_func = self.bound_functions[bound_key]

        return function_wrapper

    def __call__(self, *args, **kwargs):
        name = self.func.__name__ + str(self.calls)
        self.calls += 1
        # See concerns above about uniqueifying
        name = _uniqueify_name(name)

        return _Block(self.func, self, name, self.srcfile,
                      self.srcline, *args, **kwargs)


class _Block(object):

    def __init__(self, func, deco, name, srcfile, srcline, *args, **kwargs):
        # ic(func, deco, name)
        # calls = deco.calls

        self.func = func
        self.hdlclass = None
        if isboundmethod(func):
            if isinstance(func.__self__, HdlClass):
                self.hdlclass = func.__self__  # make a backlink to the class
                self.args = tuple([v for v in vars(func.__self__).values()])
                self.kwargs = {}
            else:
                # some other classe see test\conversion\general\test_method.py
                self.args = args
                self.kwargs = kwargs
        else:
            self.args = args
            self.kwargs = kwargs

        # ic(self.args, self.kwargs)
        self.__doc__ = func.__doc__
        callinfo = _getCallInfo(self.hdlclass)
        self.callinfo = callinfo
        self.modctxt = callinfo.modctxt
        self.callername = callinfo.name
        self.filename = callinfo.filename
        self.symdict = None
        self.sigdict = {}
        self.memdict = {}
        self.name = self.__name__ = name
        # flatten, but keep BlockInstance objects
        self.subs = _flatten(func(*args, **kwargs))
        self._verifySubs()
        self._updateNamespaces()
        # ic((self.symdict), self.sigdict, self.memdict)
        self.verilog_code = self.vhdl_code = None
        self.sim = None
        self.endhierarchy = False
        if hasattr(deco, 'verilog_code'):
            # ic((self.symdict))
            self.verilog_code = _UserVerilogCode(deco.verilog_code, self.symdict, func.__name__,
                                                 func, srcfile, srcline)
        elif hasattr(deco, 'verilog_instance'):
            self.verilog_code = _UserVerilogInstance(deco.verilog_instance, self.symdict, func.__name__,
                                                     func, srcfile, srcline)
        if hasattr(deco, 'vhdl_code'):
            self.vhdl_code = _UserVhdlCode(deco.vhdl_code, self.symdict, func.__name__,
                                           func, srcfile, srcline)
        elif hasattr(deco, 'vhdl_instance'):
            self.vhdl_code = _UserVhdlInstance(deco.vhdl_instance, self.symdict, func.__name__,
                                               func, srcfile, srcline)
        self._config_sim = {'trace': False}

    def _verifySubs(self):
        for inst in self.subs:
            # ic(vars(inst))
            if not isinstance(inst, (_Block, _Instantiator, Cosimulation)):
                raise BlockError(_error.ArgType % (self.name,))
            if isinstance(inst, (_Block, _Instantiator)):
                if not inst.modctxt:
                    raise BlockError(_error.InstanceError % (self.name, inst.callername))

    def _updateNamespaces(self):
        # ic(self.name, self.sigdict, self.memdict)
        # dicts to keep track of objects used in Instantiator objects
        usedsigdict = {}
        usedlosdict = {}
        # ic(self.subs)
        for inst in self.subs:
            # ic(inst)
            # the symdict of a block instance is defined by
            # the call context of its instantiations
            if isinstance(inst, Cosimulation):
                continue  # ignore

            if self.symdict is None:
                self.symdict = inst.callinfo.symdict
                # ic(self.symdict)

            if isinstance(inst, _Instantiator):
                # ic(inst.sigdict, inst.losdict)
                usedsigdict.update(inst.sigdict)
                usedlosdict.update(inst.losdict)

        if self.symdict is None:
            self.symdict = {}
        # Special case: due to attribute reference transformation, the
        # sigdict and losdict from Instantiator objects may contain new
        # references. Therefore, update the symdict with them.
        # To be revisited.
        # ic(self.symdict)
        # self.symdict.update(usedsigdict)
        # self.symdict.update(usedlosdict)
        # ic(usedsigdict)
        updatesymdict(self.symdict, usedsigdict)
        updatesymdict(self.symdict, usedlosdict)
        # Infer sigdict and memdict, with compatibility patches from _extractHierarchy
        for n, v in self.symdict.items():
            if isinstance(v, _Signal):
                self.sigdict[n] = v
                if n in usedsigdict:
                    v._markUsed()
                # ic(n, (v))

            if _isListOfSigs(v):
                m = _makeMemInfo(v)
                self.memdict[n] = m
                if n in usedlosdict:
                    m._used = True
                # ic(n, (m))

        # ic(self.sigdict, self.memdict)

    def _inferInterface(self):
        from myhdl.conversion._analyze import _analyzeTopFunc
        intf = _analyzeTopFunc(self.func, *self.args, **self.kwargs)
        self.argnames = intf.argnames
        self.argdict = intf.argdict

    # Public methods
    # The puropse now is to define the API, optimizations later

    def  _clear(self):
        """ Clear a number of 'global' attributes.
        This is a workaround function for cleaning up before converts.
        """
        # workaround: elaborate again for the side effect on signal attibutes
        # TODO: jb -> jck: unfortunately this may/will also take twice as long, which for big designs matters!
        # and second it will print every user debug message twice cluttering the console output
        # so there must be a better way than this *lazy* workaround
        # maybe later ...

        if self.hdlclass is not None:
            # if present it is a **backlink** tot the instantiated HdlClass
            # An HdlClass object's hdl() method does not take any args nor kwargs
            # all ports/signals (must) have resolved in the `__init__()` call
            self.func()
        else:
            self.func(*self.args, **self.kwargs)

        # reset number of calls in all blocks
        for b in myhdl._simulator._blocks:
            b.calls = 0

    def verify_convert(self):
        self._clear()
        return myhdl.conversion.verify(self)

    def analyze_convert(self):
        self._clear()
        return myhdl.conversion.analyze(self)

    def convert(self, hdl, **kwargs):
        """Converts this BlockInstance to another HDL

        Args:
            hdl (str): Target HDL; one of 
                ['Verilog', 'VHDL', 'SystemVerilog'] must be specified

            direrctory (Optional[str]): Destination folder. Defaults to current
                working dir.

            name (Optional[str]): Module and output file name. Defaults to
                `self.mod.__name__`

            hierarchical (Optional[bool|int]): Generate hierachical modules/entities
                False | 0 : flattened design (default)
                int: -1: complete hierchical conversion
                    >= 1: flatten from this level on
                    Note: specifying an `@block(endhierarchy=True)` will override this setting and the branch
                    will be flattened depending which comes first: a depth of 1 will override an
                    endhierarchy setting at level 3 as this will override a depth setting of 4
                    
            trace(Optional[bool]): Verilog only. Whether the testbench should
                dump all signal waveforms. Defaults to False.

            no_testbench (Optional[bool]): Verilog only (for now?). Specifies whether a
                testbench should be created. Defaults to False (so we tend to creat a tb).

            timescale(Optional[str]): Verilog only. Defaults to '1ns/10ps'
        """

        from myhdl.conversion._converter import Converter

        self._clear()

        if hdl in ('toVerilog', 'toVHDL'):
            ''' temporay access to deprecated converters for comparison '''
            if hdl == 'toVHDL':
                converter = myhdl.conversion._toVHDL.toVHDL
            elif hdl == 'toVerilog':
                converter = myhdl.conversion._toVerilog.toVerilog

            conv_attrs = {}
            if 'name' in kwargs:
                conv_attrs['name'] = kwargs.pop('name')
            conv_attrs['directory'] = kwargs.pop('path', '')
            if hdl.lower() == 'verilog':
                conv_attrs['no_testbench'] = not kwargs.pop('testbench', True)
                conv_attrs['timescale'] = kwargs.pop('timescale', '1ns/10ps')
                conv_attrs['trace'] = kwargs.pop('trace', False)

            conv_attrs.update(kwargs)
            for k, v in conv_attrs.items():
                setattr(converter, k, v)

        else:
            # ic(self.name, kwargs)
            converter = Converter(hdl, **kwargs)

        return converter(self)

    def config_sim(self, trace=False, **kwargs):
        self._config_sim['trace'] = trace
        if trace:
            for k, v in kwargs.items():
                setattr(myhdl.traceSignals, k, v)
            myhdl.traceSignals(self)

    def run_sim(self, duration=None, quiet=0):
        if self.sim is None:
            sim = self
            # if self._config_sim['trace']:
            #    sim = myhdl.traceSignals(self)
            self.sim = myhdl._Simulation.Simulation(sim)
        self.sim.run(duration, quiet)

    def quit_sim(self):
        if self.sim is not None:
            self.sim.quit()


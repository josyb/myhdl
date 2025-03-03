#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2012 Jan Decaluwe
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

""" 
    myhdl generic conversion module.
    29-10-2023 josyb:    initial creation
    
"""

import os
import sys
import inspect

from io import StringIO

try:
    from icecream import ic
    ''' 
        this is the only place where we configure icecream
        all other modules refrain!
    '''
    import pprint
    # the times of 80-column monitors is long gone - fuck PEP-8's Maximum Line Length
    preferredWidth = 150  # thiswill make the astdumps more readable, among others ...
    pp = pprint.PrettyPrinter(width=preferredWidth)
    ic.configureOutput(argToStringFunction=pp.pformat, outputFunction=print, includeContext=True, contextAbsPath=True,
                   prefix='')
    ic.lineWrapWidth = preferredWidth
    # ic.disable()
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl import  ConversionError
from myhdl._getHierarchy import _getHierarchy
from myhdl._Signal import _Signal, _isListOfSigs
from myhdl._block import _Block
from myhdl._extractHierarchy import _isMem, _getMemInfo
from myhdl.conversion._analyze import _analyzeSigs, _analyzeGens
from myhdl.conversion._hierarchical import (collectsubs, _HierarchicalInstance, _flattenhierarchy, _checkArgs,
                                            _HierarchicalPort, gethierarchicalmodulenames)
from myhdl.conversion._misc import _genUniqueSuffix, _kind, _makeDoc, _error
from myhdl.conversion._annotate import _annotateTypes
from myhdl.conversion._VHDLwriter import VhdlWriter
from myhdl.conversion._Verilogwriter import VerilogWriter
from myhdl.conversion._SystemVerilogwriter import SystemVerilogWriter

_converting = 0


class Converter(object):

    def __init__(self, hdl, **kwargs):
        assert hdl in ['VHDL', 'Verilog', 'SystemVerilog']
        self.hdl = hdl
        # process the common kwargs
        self.name = None
        self.directory = ''
        self.no_testbench = False
        self.hierarchical = False
        self.trace = False
        for key, value in kwargs.items():
            if key in ['name', 'directory', 'hierarchical', 'no_testbench', 'trace', 'sourcepath']:
                setattr(self, key, value)

        # select the appropriate HDL Writer
        # and apply the (remaining) kwargs
        if hdl == 'VHDL':
            self.writer = VhdlWriter(**kwargs)
        elif hdl == 'Verilog':
            self.writer = VerilogWriter(**kwargs)
        elif hdl == 'SystemVerilog':
            self.writer = SystemVerilogWriter(**kwargs)
        else:
            raise ConversionError(_error.UnkownConvertor, hdl)

    def __call__(self, func, *args, **kwargs):

# TODO: check whether _converting and _tracing have any effect
        global _converting
        if _converting:
            # NOTE _block.py calls us with empty args and empty kwargs ...
            return func(*args, **kwargs)  # skip
        else:
            # clean start
            sys.setprofile(None)

        from myhdl import _traceSignals
        if _traceSignals._tracing:
            raise ConversionError("Cannot use Converter while tracing signals")

        _converting = 1
        if self.name is None:
            self.name = func.func.__name__

        ic(self.name)

        try:
            h = _getHierarchy(self.name, func)
        finally:
            _converting = 0
            pass

        # report the hierarchy
        # ic(h, h.top, h.hierarchy, h.absnames)

        ### initialize properly ###
        _genUniqueSuffix.reset()

        if self.hierarchical:
            ic("Going hierarchical!")

            ha = []
            collectsubs(h.top, maxdepth=self.hierarchical, hdl=self.hdl, hierarchy=ha)  # give it an empty list as a placeholder
            # now start converting 'bottoms up'
            # we need an empty directory where we place all output files
            # we will erase any existing files ...
            self.directory = f'{self.name}'
            if not os.path.exists(self.directory):
                # create it
                os.mkdir(self.directory)
            else:
                # clean it
                with os.scandir(self.directory) as entries:
                    for entry in entries:
                        if entry.is_file():
                            os.unlink(entry.path)

            modules = {}

            startlevel = len(ha) - 1
            # ic(ha, startlevel)
            for ll in range(startlevel, -1, -1):
                # ic(ll, (ha[ll]))
                for bb in ha[ll]:
                    # ic('======================================', bb)
                    # we normally only need one level of hierarchy
                    # unless we choose to flatten a part of the code
                    # ic(vars(bb.blocksubs))
                    # for ssub in bb.blocksubs.subs:
                    #     ic(ssub, vars(ssub))
                    # if bb.blocksubs.hdlclass is not None:
                    #     ic(bb.blocksubs.hdlclass)

                    # ic(bb.instancename, bb.blocksubs, bb.blocksubs.endhierarchy)
                    bbh = _getHierarchy(bb.instancename, bb.blocksubs, descend=bb.blocksubs.endhierarchy or (ll == startlevel))
                    # ic(bbh, bbh.top, bbh.hierarchy, bb.gens)

                    genlist = _analyzeGens(bb.gens, bbh.absnames)
                    # ic(genlist, bb.blocksubs, len(bb.blocksubs.subs), bb.blocksubs.subs,
                    #    bb.blocksubs.args, bb.blocksubs.kwargs, bb.blocksubs.sigdict)

                    # see if we have an already generated file for this block
                    subsoutputports = []
                    for sub in bb.blocksubs.subs:
                        if sub.name in modules:
                            # ic(f'{ll} found {sub.name} in generated modules', repr(modules[sub.name]))
                            # ic(vars(sub))
                            # add the found generated module to the list
                            genlist.insert(0, modules[sub.name])
                            # add all output ports to a
                            for port in modules[sub.name].argports:
                                subsoutputports.append(modules[sub.name].argports[port])

                    # ic(genlist, subsoutputports)

                    # _analyzeSigs will skip signals that have been treated at a lower level
                    # invalidating the name will force a re-evaluation
                    # also, some of the subblocks will use input-only signal from a higher level
                    # which has been generated/treated by another module and also have the _driven attribute set
                    # in which case this signal gets flagged as an output
                    # so whave to reset the ._driven for these specific signals only
                    # ic((bb.blocksubs.sigdict))
                    for __, s in bb.blocksubs.sigdict.items():
                        # ic(ll, s._info)
                        # s._name = None
                        if ll:
                            if s._driver == 'driven':
                                s._driver = bb.instancename

                            # if s._read:
                            #     if len(s._readers):
                            #         if s._readers[-1] == 'read':
                            #             s._readers[-1] = bb.instancename
                            #
                            #         else:
                            #             s._readers.append(bb.instancename)
                            #
                            #     else:
                            #         s._readers.append(bb.instancename)

                        else:
                            # if s._read:
                            #     s._readers = []

                            if s._driver is not None:
                                s._driver = 'driven'
                        # ic(ll, s._info)

                    siglist, memlist = _analyzeSigs(bbh.hierarchy, hdl=self.hdl)
                    # info = [(id(item), repr(item), item._driven, item._read) for item in siglist]
                    # ic(info)

                    _annotateTypes(self.hdl, genlist)
                    # siglistinfo = [ sig._info for sig in siglist]
                    # ic(ll, bb.instancename, siglistinfo, bb.blocksubs, bb.blocksubs)

                    res = self._convert(ll, bb.instancename, bbh, bb.blocksubs, siglist, memlist, genlist, subsoutputports)
                    # build the 'placeholder' information for this block
                    # as it may be called upon by the next higher code level
                    # save the converted block information
                    sl = []
                    argports = {}
                    for argname in res.argnames:
                        s = res.argdict[argname]
                        sl.append(s)
                        if isinstance(s, _Signal):
                            if s._driven:
                                argports[argname] = _HierarchicalPort(s)
                        elif _isMem(s):
                            m = _getMemInfo(s)
                            if m._driven:
                                argports[argname] = _HierarchicalPort(s)
                    # !!! the cleanup later will 'destroy' some of the information on the signals
                    # which we need ...
                    # else there will be no output ports ...
                    # so we have to keep a deepcopy' instead
                    # or perhaps make a new class?
                    # ic(bb.instancename, res, res.argnames, res.argdict, res.sigdict, sl)
                    argportsinfo = []
                    for arg in argports:
                        argportsinfo.append(argports[arg]._info)
                    # ic(argportsinfo)

                    modules[bb.instancename] = _HierarchicalInstance(self.writer, bb.instancename, res.argnames, sl, argports)

                    ### clean-up properly ###
                    # self._cleanup(siglist, memlist)
                    for sig in siglist:
                        # sig._clear()
                        sig._name = None
                        sig._inList = False
                        for sl in sig._slicesigs:
                            sl._name = None
                            sl._inList = False

                    for mem in memlist:
                        mem.name = None
                        for s in mem.mem:
                            # s._clear()
                            s._name = None
                            s._inList = False
                            for sl in s._slicesigs:
                                sl._name = None
                                sl._inList = False

                    argportsinfo = []
                    for arg in argports:
                        argportsinfo.append(argports[arg]._info)
                    # ic(argportsinfo)
                    # ic(modules)
            # we sould return something useful
            # e.g.: the collected subs?
            # ic(ha)
            res = gethierarchicalmodulenames(ha)
            # ic(res)
            # we need the block object ...
            # python allows us to add attributes at run-time, without a whisper ...
            h.top.modules = res

        else:
            # TODO: check if we can refactor this code into the 'generic hierachical' branch
            ic('We flatten the design')

            arglist = _flattenhierarchy(self.hdl, h.top)
            _checkArgs(arglist)
            genlist = _analyzeGens(arglist, h.absnames)
            siglist, memlist = _analyzeSigs(h.hierarchy, hdl=self.hdl)
            # ic(h, h.top, h.hierarchy)
            # generic annotate for 'all' target HDLs
            _annotateTypes(self.hdl, genlist)

            self._convert(0, self.name, h, func, siglist, memlist, genlist)

        return h.top

    def _convert(self, level, name, h, func, siglist, memlist, genlist, subsoutputports=None):

        # ic(level, name, h, func, func.args, siglist, memlist, genlist)
        # finally
        if func.hdlclass is not None:
            # if present it is a **backlink** tot the instantiated HdlClass
            ports = []
            # func.hdlclass.__dict__ is made by the __init__ call on class instantiation
            # ic(func.hdlclass, func.hdlclass.__dict__)
            for n, s in func.hdlclass.__dict__.items():
                ic(n, s, _isListOfSigs(s))
                # TODO: look out for interfaces (and structures, lists etc in the future)
                if isinstance(s, _Signal):
                    # if s._name is None:
                    s._name = n
                    ports.append(s)

                elif _isMem(s):
                    m = _getMemInfo(s)
                    m.name = n
                    ports.append(s)

                # elif _isListOfSigs(s):
                #     # ic(s)
                #     # no name yet ...?
                #     ports.append(s)

                elif isinstance(s, _Block):
                    # skip
                    pass

                elif hasattr(s, '__dict__'):
                    # the 'anonymous' interface ...
                    s._name = n
                    ports.append(s)

            ic(ports)
            func.args = tuple(ports)

        # infer interface after signals have been analyzed
        func._inferInterface(self.hdl)
        intf = func
        intf.name = name

        if self.hierarchical:
            # update the ports as their _driven and _read atributes have been reset after the submodule generation
            # which will default (some) ports to input iso output
            for subport in subsoutputports:
                if subport.obj._name in intf.argdict:
                    intf.argdict[subport.obj._name]._driven = subport._driven

        # start the output file, only when the analysis/annotation process passes
        self.writer.openfile(name, self.directory)

        doc = _makeDoc(inspect.getdoc(func), self.writer.comment)
        self._convert_filter(h, intf, doc, siglist, memlist, genlist)

        # all this gets delegated to the respective writer
        self.writer.writePackages(self.directory)
        self.writer.writeModuleHeader(intf, func.filename)
        self.writer.writeDecls(intf, siglist, memlist)

        self._convertGens(genlist)

        # almost done
        self.writer.writeModuleFooter()

        if level == 0:
            # build portmap for cosimulation (but only for toplevel)
            portmap = {}
            for n, s in intf.argdict.items():
                if hasattr(s, 'driver'):
                    # tristate signal !!
                    # confusing with _driver in hierachical
                    portmap[n] = s.driver()
                else:
                    portmap[n] = s
            self.writer.portmap = portmap

        self.writer.close()

        # if not self.hierarchical:
        if level == 0:
            # don't write testbench if module has no ports
            if len(intf.argnames) > 0 and not self.no_testbench:
                self.writer._writeTestBench(self.directory, name, intf, self.trace)

            ### clean-up properly ###
            self._cleanup(siglist, memlist)

            # return the 'processed' hierarchy
            return h.top
        else:
            return intf

    def _convert_filter(self, h, intf, doc, siglist, memlist, genlist):
        # intended to be a entry point for other uses:
        #  code checking, optimizations, etc
        pass

    def _cleanup(self, siglist, memlist):
        # clean up signals
        for sig in siglist:
            sig._clear()
        for mem in memlist:
            mem.name = None
            for s in mem.mem:
                s._clear()

        # clean up attributes
        self.name = None
        self.writer._cleanup()

    def _convertGens(self, genlist):
        blockBuf = StringIO()
        funcBuf = StringIO()
        # ic(genlist)
        for tree in genlist:
            if isinstance(tree, self.writer.usercode) or isinstance(tree, _HierarchicalInstance):
                blockBuf.write(str(tree))
                continue

            # ic(tree, tree.kind)
            if tree.kind == _kind.ALWAYS:
                Visitor = self.writer.ConvertAlwaysVisitor
            elif tree.kind == _kind.INITIAL:
                Visitor = self.writer.ConvertInitialVisitor
            elif tree.kind == _kind.SIMPLE_ALWAYS_COMB:
                Visitor = self.writer.ConvertSimpleAlwaysCombVisitor
            elif tree.kind == _kind.ALWAYS_DECO:
                Visitor = self.writer.ConvertAlwaysDecoVisitor
            elif tree.kind == _kind.ALWAYS_SEQ:
                Visitor = self.writer.ConvertAlwaysSeqVisitor
            else:  # ALWAYS_COMB
                Visitor = self.writer.ConvertAlwaysCombVisitor
            v = Visitor(tree, blockBuf, funcBuf, self.writer)
            v.visit(tree)
        self.writer.file.write(funcBuf.getvalue())
        funcBuf.close()
        self.writer.file.write(blockBuf.getvalue())
        blockBuf.close()


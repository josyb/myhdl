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

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True,
                   prefix='')
# ic.disable()
import pprint
pp = pprint.PrettyPrinter(indent=4, width=120)

from myhdl import  ConversionError
from myhdl._getHierarchy import _getHierarchy
from myhdl.conversion._analyze import _analyzeSigs, _analyzeGens
from myhdl.conversion._hierarchical import collectsubs, _HierarchicalInstance, getargnames, _flattenhierarchy, _checkArgs
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
            print(f"{key} = {value}")
            if key in ['name', 'directory', 'hierarchical', 'no_testbench', 'trace']:
                setattr(self, key, value)
                # # drop it?
                # del kwargs[key]

        # select the appropriate HDL Writer
        # and apply the remaining kwargs
        if hdl == 'VHDL':
            self.writer = VhdlWriter(**kwargs)
        elif hdl == 'Verilog':
            self.writer = VerilogWriter(**kwargs)
        elif hdl == 'SystemVerilog':
            self.writer = SystemVerilogWriter(**kwargs)
        else:
            raise ConversionError(_error.UnkownConvertor, hdl)

    def __call__(self, func, *args, **kwargs):

        global _converting
        if _converting:
            # NOTE _block.py calls us with empty args and empty kwargs ...
            # ic('Help, we\'re already converting?')
            return func(*args, **kwargs)  # skip
        else:
            # clean start
            sys.setprofile(None)

        from myhdl import _traceSignals
        if _traceSignals._tracing:
            raise ConversionError("Cannot use Converter while tracing signals")

        # _converting = 1
        if self.name is None:
            self.name = func.func.__name__

        ic(f'Converter: call(): {self.name}')

        try:
            h = _getHierarchy(self.name, func)
        finally:
            # _converting = 0
            pass

        # report the hierarchy
        ic(h, h.top, h.hierarchy, h.absnames)

        ### initialize properly ###
        _genUniqueSuffix.reset()

        if self.hierarchical:
            # ic("Going hierarchical!")

            ha = []
            collectsubs(h.top, maxdepth=self.hierarchical, hdl=self.hdl, hierarchy=ha) # give it an empty list as a placeholder
            ic(pp.pformat(ha))

            # now start converting 'bottoms up'
            # we need an empty directory where we place all output
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
            for ll in range(startlevel, -1, -1):
                ic(ll, pp.pformat(ha[ll]))
                for bb in ha[ll]:
                    ic('======================================')
                    ic(bb)
                    # we normally only need one level of hierarchy
                    # unless we choose to flatten a certian part of the code
                    ic(bb.blocksubs.endhierarchy)
                    if ll == startlevel:
                        bbh = _getHierarchy(bb.instancename, bb.blocksubs, descend=True)
                    else:
                        bbh = _getHierarchy(bb.instancename, bb.blocksubs, descend=bb.blocksubs.endhierarchy)
                    ic(pp.pformat(bbh))
                    ic(pp.pformat(bbh.top))
                    ic(pp.pformat(bbh.hierarchy))
                    ic(pp.pformat(bb.gens))
                    genlist = _analyzeGens(bb.gens, bbh.absnames)
                    ic(pp.pformat(genlist))

                    ic(bb.blocksubs)
                    ic(len(bb.blocksubs.subs), bb.blocksubs.subs)
                    ic(bb.blocksubs.args)
                    ic(bb.blocksubs.kwargs)
                    ic(bb.blocksubs.sigdict)
                    for i, sub in enumerate(bb.blocksubs.subs):
                        if sub.name in modules:
                            ic(f'{ll} found {sub.name} in generated {modules=}')
                            ic(f'{vars(sub)=}')
                            # add the found generated module to the list
                            genlist.insert(0, modules[sub.name])

                    ic(pp.pformat(genlist))

                    # _analyzeSigs will skip signals that have been treated at a lower level
                    # invalidating the name will force a re-evaluation
                    ic(pp.pformat(bb.blocksubs.sigdict))
                    for __, s in bb.blocksubs.sigdict.items():
                        s._name = None
                        ic(f'{s._driver=}')
                        if ll:
                            if s._driver == 'driven':
                                s._driver = bb.instancename
                        else:
                            if s._driver is not None:
                                s._driver = 'driven'
                        ic(f'{s._driver}')

                    # some of the subblocks will use input-only signal from a higher level
                    # which has been generated/treated by another module and also have the _driven attribute set
                    # in which case this signal gets flagged as an output
                    # so whave to reset the ._driven for these specific signals only
                    argnames = getargnames(bb.blocksubs)
                    ic(argnames)

                    siglist, memlist = _analyzeSigs(bbh.hierarchy, hdl=self.hdl)
                    ic(pp.pformat(siglist))
                    ic(pp.pformat(memlist))
                    for item in siglist:
                        ic(f'  {id(item)} {repr(item)} {item._driven=} {item._read=}')

                    _annotateTypes(self.hdl, genlist)

                    res = self._convert(ll, bb.instancename, bbh, bb.blocksubs, siglist, memlist, genlist)
                    ic(f'{res=}')
                    # build the 'placeholder' information for this block
                    # as it may be called upon by the next higher code level
                    # save the converted block information
                    sl = []
                    for argname in res.argnames:
                        s = res.sigdict[argname]
                        sl.append(s)
                    modules[bb.instancename] = _HierarchicalInstance(self.writer, bb.instancename, res.argnames, sl)

        else:
            ic('We flatten the design')

            arglist = _flattenhierarchy(self.hdl, h.top)
            ic(arglist)
            _checkArgs(arglist)
            ic(pp.pformat(arglist))

            genlist = _analyzeGens(arglist, h.absnames)
            ic(pp.pformat(genlist))

            siglist, memlist = _analyzeSigs(h.hierarchy, hdl=self.hdl)
            ic(siglist, memlist)
            for m in memlist:
                ic(m.name)
            ic(h, h.top, h.hierarchy, pp.pformat(siglist), memlist)
            for m in memlist:
                ic(m.name)
            # generic annotate for 'all' target HDLs
            _annotateTypes(self.hdl, genlist)
            for m in memlist:
                ic(m.name)

            self._convert(0, self.name, h, func, siglist, memlist, genlist)

            return h.top

    def _convert(self, level, name, h, func, siglist, memlist, genlist):

        # finally
        # infer interface after signals have been analyzed
        func._inferInterface()
        intf = func
        intf.name = name
        ic(func, vars(func))

        # start the output file, only when the analysis/annotation process passes
        self.writer.openfile(name, self.directory)

        doc = _makeDoc(inspect.getdoc(func), self.writer.comment)
        self._convert_filter(h, intf, doc, siglist, memlist, genlist)

        # all this gets delegated to the respective writer
        self.writer.writePackages(self.directory)
        self.writer.writeModuleHeader(intf)
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

        if not self.hierarchical:
            # don't write testbench if module has no ports
            if len(intf.argnames) > 0 and not self.no_testbench:
                tbpath = os.path.join(self.directory, "tb_" + name + ".v")
                tbfile = open(tbpath, 'w')
                self.writer._writeTestBench(tbfile, intf, self.trace)
                tbfile.close()

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
        for tree in genlist:
            ic(f'_convertGens: {tree=}')
            if isinstance(tree, self.writer.usercode) or isinstance(tree, _HierarchicalInstance):
                blockBuf.write(str(tree))
                continue

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
            else: # ALWAYS_COMB
                Visitor = self.writer.ConvertAlwaysCombVisitor
            v = Visitor(tree, blockBuf, funcBuf, self.writer)
            v.visit(tree)
        self.writer.file.write(funcBuf.getvalue())
        funcBuf.close()
        self.writer.file.write(blockBuf.getvalue())
        blockBuf.close()


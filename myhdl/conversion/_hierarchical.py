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
import ast
from collections import namedtuple
from types import GeneratorType

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True)
from astpretty import pformat as astdump
import pprint
pp = pprint.PrettyPrinter(indent=4)

from myhdl import  ConversionError
from myhdl._instance import _Instantiator
from myhdl._block import _Block
from myhdl._extractHierarchy import  _userCodeMap, _UserCode, _isMem, _getMemInfo
from myhdl._Signal import _Signal, _isListOfSigs
from myhdl._util import _makeAST
from myhdl._misc import isboundmethod
from myhdl._enum import EnumType
from myhdl._hdlclass import HdlClass
from myhdl.conversion._misc import _error, _get_argnames, _ConversionMixin

LevelInfo = namedtuple('LevelInfo', ['modulename', 'instancename', 'blocksubs' , 'gens'])


def _checkArgs(arglist):
    ic(pp.pformat(arglist))
    for arg in arglist:
        ic(repr(arg))
        if not isinstance(arg, (GeneratorType, _Instantiator, _UserCode)):
            raise ConversionError(_error.ArgType, arg)


def _flattenhierarchy(hdl, *args):
    # ic(pp.pformat(args))
    arglist = []
    for arg in args:
        if isinstance(arg, _Block):
            if hdl == 'Verilog':
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

        if id(arg) in _userCodeMap[hdl]:
            arglist.append(_userCodeMap[hdl][id(arg)])
        elif isinstance(arg, (list, tuple, set)):
            for item in arg:
                arglist.extend(_flattenhierarchy(hdl, item))
        else:
            arglist.append(arg)

    return arglist


def reportsubs(subs, hdl, level=0, name_prefixes=[], hierarchy=[]):
    if isinstance(subs, _Block):
        # ic(f'{level:2} {level*"  "}{subs.name} : {name_prefixes=} -> _Block {subs.subs=}')
        # ic(f'{len(hierarchy)=} {level=}')
        if len(hierarchy) < level + 1:
            # start the first or new level
            hierarchy.append([])

        if subs.endhierarchy:
            # walk down
            gens = _flattenhierarchy(hdl, subs.subs)
        else:
            # only local generators
            gens = [ss for ss in subs.subs if not isinstance(ss, _Block)]

        # snaity check
        _checkArgs(gens)
        # now append
        hierarchy[level].append(LevelInfo(subs.name, '_'.join(name_prefixes) if level > 0 else subs.name, subs, gens))

        if not subs.endhierarchy:
            reportsubs(subs.subs, hdl, level, name_prefixes, hierarchy)

    elif isinstance(subs, (list, tuple, set)):
        for sub in subs:
            name_prefixes.append(sub.name)
            reportsubs(sub, hdl, level + 1, name_prefixes, hierarchy)
            name_prefixes.pop(-1)

    else:
        pass


class _HierarchicalInstance(object):
    # __slots__ = ['hdlwriter', 'name', 'namespace', 'funcname', 'func', 'sourcefile', 'sourceline']

    # def __init__(self, hdlwriter, code, namespace, funcname, func, sourcefile, sourceline):
    def __init__(self, hdlwriter, name, argnames, argsigs):
        self.hdlwriter = hdlwriter
        self.name = name
        self.argnames = argnames
        self.sigdict = argsigs
        # self.sourcefile = sourcefile
        # self.func = func
        # self.funcname = funcname
        # self.sourceline = sourceline

    def __str__(self):
        # try:
        #     code = self._interpolate()
        # except:
        #     exctype, value, __ = sys.exc_info()
        #     info = "in file %s, function %s starting on line %s:\n    " % \
        #            (self.sourcefile, self.funcname, self.sourceline)
        #     msg = "%s: %s" % (exctype, value)
        #     self.raiseError(msg, info)
        # code = "\n%s\n" % code
        # return code
        return self.hdlwriter.hierarchicalinstance(self)
    #
    # def _scrub_namespace(self):
    #     for nm, obj in self.namespace.items():
    #         if _isMem(obj):
    #             memi = _getMemInfo(obj)
    #             self.namespace[nm] = memi.name
    #
    # def _interpolate(self):
    #     self._scrub_namespace()
    #     return string.Template(self.code).substitute(self.namespace)

# # a local function to drill down to the last interface
# def expandinterface(v, name, obj):
#     for attr, attrobj in vars(obj).items():
#         if isinstance(attrobj, _Signal):
# # override any 'mangled' name
# #             signame = attrobj._name
# #             if not signame:
#             signame = name + '_' + attr
#             attrobj._name = signame
#             v.argdict[signame] = attrobj
#             v.argnames.append(signame)
#         elif isinstance(attrobj, EnumType):
#             pass
#         elif hasattr(attrobj, '__dict__'):
#             # can assume is yet another interface ...
#             expandinterface(v, name + '_' + attr, attrobj)


def getargnames(func):
    ic(pp.pformat(func))
    tree = _makeAST(func.func)
    v = _AnalyzeTopFuncVisitor(func.func, tree, func.args, func.kwargs)
    v.visit(tree)
    #
    # objs = []
    # for name, obj in v.fullargdict.items():
    #     if not isinstance(obj, _Signal):
    #         objs.append((name, obj))
    #
    # # create ports for any signal in the top instance if it was buried in an
    # # object passed as in argument
    #
    # # now expand the interface objects
    # for name, obj in objs:
    #     if hasattr(obj, '__dict__'):
    #         # must be an interface object (probably ...?)
    #         expandinterface(v, name, obj)

    return v.argnames


class _AnalyzeTopFuncVisitor(ast.NodeVisitor, _ConversionMixin):
    '''
        this visitor will only analyze the Function
        I assume that all other nodes will be visited by the generic-visitor 
        which does nothing and has no (side-)effects? 
    '''

    def __init__(self, func, tree, *args, **kwargs):
        self.func = func
        self.tree = tree
        self.args = args
        self.kwargs = kwargs
        self.name = None
        self.fullargdict = {}
        self.argdict = {}
        self.argnames = []

    def visit_FunctionDef(self, node):
        # ic(astdump(node, show_offsets=False))

        self.name = node.name
        if isboundmethod(self.func):
            if isinstance(self.func.__self__, HdlClass):
                # must find names ...
                for arg in self.args:
                    # be selective
                    if isinstance(arg, _Signal):
                        self.argnames.append(arg._name)
                    elif _isListOfSigs(arg):
                        raise NotImplementedError(f'do not handle ListOfSignals {self.name}:{arg}')

            else:
                # another class
                self.argnames = _get_argnames(node)
                if not self.argnames[0] == 'self':
                    self.raiseError(node, _error.NotSupported,
                                    "first method argument name other than 'self'")
                # skip self
                self.argnames = self.argnames[1:]

        else:
            self.argnames = _get_argnames(node)

        i = -1
        for i, arg in enumerate(self.args):
            n = self.argnames[i]
            self.fullargdict[n] = arg
            if isinstance(arg, _Signal):
                self.argdict[n] = arg

            if _isMem(arg):
                self.raiseError(node, _error.ListAsPort, n)

        for n in self.argnames[i + 1:]:
            if n in self.kwargs:
                arg = self.kwargs[n]
                self.fullargdict[n] = arg
                if isinstance(arg, _Signal):
                    self.argdict[n] = arg

                if _isMem(arg):
                    self.raiseError(node, _error.ListAsPort, n)

        self.argnames = [n for n in self.argnames if n in self.argdict]

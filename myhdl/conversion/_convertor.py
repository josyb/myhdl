'''
Created on 1 jan. 2020

@author: josy
'''

import sys
import inspect
import ast
import warnings
from types import GeneratorType

import astpretty

from myhdl import ConversionError, intbv

from myhdl._block import _Block
from myhdl._compat import integer_types, class_types, PY2
from myhdl._extractHierarchy import (_HierExtr, _isMem, _getMemInfo,
                                     _UserVhdlCode, _userCodeMap,
                                     _UserVerilogCode)
from myhdl._instance import _Instantiator
from myhdl._getHierarchy import _getHierarchy

from myhdl.conversion._misc import (_error, _kind, _context,
                                    _ConversionMixin, _Label, _genUniqueSuffix, _isConstant)
from myhdl.conversion._analyze import (_analyzeSigs, _analyzeGens, _analyzeTopFunc,
                                       _Ram, _Rom, _enumTypeSet)

supportedhdls = ['verilog',
                 'vhdl',
                 # any others?
                 ]
hdlcomments = { 'verilog': '// ',
            'vhdl': '-- ',
            # any others?
            }
hdlusercodes = { 'verilog': _UserVerilogCode,
            'vhdl': _UserVhdlCode,
            # any others?
            }

# used for name validation
_usedNames = []

_converting = 0


def _checkArgs(arglist, hdl=None):
    for arg in arglist:
        if not isinstance(arg, (GeneratorType, _Instantiator, hdlusercodes[hdl])):
            raise ConversionError(_error.ArgType, arg)


def _flatten(*args, hdl=None):
    arglist = []
    for arg in args:
        if isinstance(arg, _Block):
            if hdl == 'verilog':
                if arg.verilog_code is not None:
                    arglist.append(arg.verilog_code)
                    continue
                else:
                    arg = arg.subs
            elif hdl == 'vhdl':
                if arg.vhdl_code is not None:
                    arglist.append(arg.vhdl_code)
                    continue
                else:
                    arg = arg.subs

        if id(arg) in _userCodeMap[hdl]:
            arglist.append(_userCodeMap[hdl][id(arg)])
        elif isinstance(arg, (list, tuple, set)):
            for item in arg:
                arglist.extend(_flatten(item, hdl=hdl))
        else:
            arglist.append(arg)

    return arglist


hdlcomments = { 'verilog': '// ',
            'vhdl': '-- ',
            # any others?
            }
hdlusercodes = { 'verilog': _UserVerilogCode,
            'vhdl': _UserVhdlCode,
            # any others?
            }
supportedhdls = ['verilog', 'vhdl']


def _makeDoc(doc, hdl, indent=''):
    if doc is None:
        return ''
    commentstart = hdlcomments[hdl]
    doc = inspect.cleandoc(doc)
    pre = '\n' + indent + commentstart
    doc = commentstart + doc
    doc = doc.replace('\n', pre)
    return doc


class HdlConvertor(object):
    # no __slots__ specified!

    def __init__(self):
        self.name = None
        self.directory = None
        self.initial_values = False
        # all others will be added by the block
#         self.component_declarations = None
#         self.header = ''
#         self.no_myhdl_header = False
#         self.no_myhdl_package = False
#         self.library = "work"
#         self.use_clauses = None
#         self.architecture = "MyHDL"
#         self.std_logic_ports = False

    def __call__(self, func, *args, **kwargs):
        print(self.hdl)
        global _converting
        if _converting:
            return func(*args, **kwargs)  # skip
        else:
            # clean start
            sys.setprofile(None)
        from myhdl import _traceSignals
        if _traceSignals._tracing:
            raise ConversionError("Cannot use convert while tracing signals")

        if not isinstance(func, _Block):
            raise ConversionError(_error.NotSupported, 'need @block decorator')

        # clear out the list of user declared Signal (and other?) names
        del _usedNames[:]

        _converting = 1
        if self.name is None:
            name = func.__name__
            if isinstance(func, _Block):
                name = func.func.__name__
        else:
            name = str(self.name)

        try:
            h = _getHierarchy(name, func)
            # dump to the debug file
            print('hierarchy:')
            for item in h.hierarchy:
                print(item)

            print('\nabsnames:')
            print(h.absnames)
        finally:
            _converting = 0

        if self.directory is None:
            directory = ''
        else:
            directory = self.directory

        ### initialize properly ###
        _genUniqueSuffix.reset()
        # ToDo VHDL only, defer until later
#         _enumTypeSet.clear()
#         _enumPortTypeSet.clear()

        arglist = _flatten(h.top, hdl=self.hdl)
        _checkArgs(arglist, hdl=self.hdl)
        genlist = _analyzeGens(arglist, h.absnames)
        print('\ngenlist:')
        print(genlist)
        for gen in genlist:
            astpretty.pprint(gen)

        siglist, memlist = _analyzeSigs(h.hierarchy, hdl='VHDL')
#         print(h.top)
        _annotateTypes(genlist)
        print('\nannotated genlist:')
        for gen in genlist:
            astpretty.pprint(gen)

        # infer interface after signals have been analyzed
        func._inferInterface()
        intf = func

        # ToDo HDL dependent, defere until later
#         doc = _makeDoc(inspect.getdoc(func), hdl=)
        # any other pre-processing?
        self._convert_filter(h, intf, siglist, memlist, genlist)

        # this was the first pass
        # now have an annotates AST
        # let's dump it to a file

        # finally
        return h.top

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
        self.standard = '2001'
        self.prefer_blocking_assignments = True
        self.radix = ''
        self.header = ""
        self.no_myhdl_header = False
        self.no_testbench = False
        self.trace = False

    def _convert_filter(self, h, intf, siglist, memlist, genlist):
        # intended to be a entry point for other uses:
        #  code checking, optimizations, etc
        pass


def _maybeNegative(obj):
    if hasattr(obj, '_min') and (obj._min is not None) and (obj._min < 0):
        return True
    if isinstance(obj, integer_types) and obj < 0:
        return True
    return False


class _AnnotateTypesVisitor(ast.NodeVisitor, _ConversionMixin):

    def __init__(self, tree):
        self.tree = tree

    def visit_FunctionDef(self, node):
        # don't visit arguments and decorators
        node.kilroy = 'Kilroy was here'
        for stmt in node.body:
            self.visit(stmt)

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.visit(node.right)
        node.signed = node.left.signed or node.right.signed
        # special treatement of subtraction unless in a top-level rhs
        if isinstance(node.op, ast.Sub) and not hasattr(node, 'isRhs'):
            node.signed = True

    def visit_BoolOp(self, node):
        for n in node.values:
            self.visit(n)
        node.signed = False

    def visit_UnaryOp(self, node):
        self.visit(node.operand)
        node.signed = node.operand.signed
        if isinstance(node.op, ast.USub):
            node.obj = int(-1)
            if isinstance(node.operand, ast.Num):
                node.signed = True

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Store):
            self.setAttr(node)
        else:
            self.getAttr(node)

    def setAttr(self, node):
        self.visit(node.value)

    def getAttr(self, node):
        node.signed = False
        self.visit(node.value)

    def visit_Call(self, node):
        self.generic_visit(node)
        f = self.getObj(node.func)
        node.signed = False
        # surprise: identity comparison on unbound methods doesn't work in python 2.5??
        if f == intbv.signed:
            node.signed = True
        elif hasattr(node, 'tree'):
            v = _AnnotateTypesVisitor(node.tree)
            v.visit(node.tree)
            node.signed = _maybeNegative(node.tree.returnObj)

    def visit_Compare(self, node):
        node.signed = False
        # for n in ast.iter_child_nodes(node):
        for n in [node.left] + node.comparators:
            self.visit(n)
            if n.signed:
                node.signed = True

    def visit_If(self, node):
        if node.ignore:
            return
        self.generic_visit(node)

    def visit_Num(self, node):
        node.signed = False

    def visit_Str(self, node):
        node.signed = False

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.setName(node)
        else:
            self.getName(node)

    def setName(self, node):
        pass

    def getName(self, node):
        node.signed = _maybeNegative(node.obj)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            self.accessSlice(node)
        else:
            self.accessIndex(node)

    def accessSlice(self, node):
        node.signed = False
        self.generic_visit(node)

    def accessIndex(self, node):
        node.signed = _maybeNegative(node.obj)
        self.generic_visit(node)

    def visit_Tuple(self, node):
        node.signed = False
        self.generic_visit(node)


def _annotateTypes(genlist):
    for tree in genlist:
        # skip any usercode
        for hdl in supportedhdls:
            if isinstance(tree, hdlusercodes[hdl]):
                continue
        v = _AnnotateTypesVisitor(tree)
        v.visit(tree)


if __name__ == '__main__':
    pass

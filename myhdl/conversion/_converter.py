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
import sys
import math

import ast
from io import StringIO

from types import GeneratorType

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True)

from astpretty import pformat as astdump

import pprint
pp = pprint.PrettyPrinter(indent=4, width=120)

from myhdl import  ConversionError
from myhdl._extractHierarchy import (_isMem, _getMemInfo, _userCodeMap)
from myhdl._instance import _Instantiator
from myhdl._Signal import _Signal, posedge, negedge
from myhdl._intbv import intbv
from myhdl._modbv import modbv
from myhdl._enum import EnumItemType, EnumType
from myhdl._concat import concat
from myhdl._block import _Block
from myhdl._getHierarchy import _getHierarchy
from myhdl._simulator import now
from myhdl._delay import delay
from myhdl.conversion._analyze import (_analyzeSigs, _analyzeGens, _Ram, _Rom)
from myhdl.conversion._misc import (_error, _kind, _context, _makeDoc, _ConversionMixin,
                                    _Label, _genUniqueSuffix, _isConstant)
from myhdl.conversion._VHDLwriter import VhdlWriter
from myhdl.conversion._Verilogwriter import VerilogWriter
from myhdl.conversion._SystemVerilogwriter import SystemVerilogWriter

# TEMPORARY imports
from myhdl.conversion._toVerilog import toVerilog

_converting = 0


def _checkArgs(arglist, usercode):
    for arg in arglist:
        if not isinstance(arg, (GeneratorType, _Instantiator, usercode)):
            raise ConversionError(_error.ArgType, arg)


def _flatten(hdl , *args):
    arglist = []
    for arg in args:
        if isinstance(arg, _Block):
            if arg.verilog_code is not None:
                arglist.append(arg.verilog_code)
                continue
            else:
                arg = arg.subs
        if id(arg) in _userCodeMap['verilog']:
            arglist.append(_userCodeMap['verilog'][id(arg)])
        elif isinstance(arg, (list, tuple, set)):
            for item in arg:
                arglist.extend(_flatten(hdl, item))
        else:
            arglist.append(arg)
    return arglist


class _Converter(object):

    def __init__(self, hdl, **kwargs):
        assert hdl in ['VHDL', 'Verilog', 'SystemVerilog']
        # process the common kwargs
        self.name = None
        self.directory = ''
        for key, value in kwargs.items():
            ic("{0} = {1}".format(key, value))
            if key in ['name', 'directory']:
                setattr(self, key, value)
                # drop it?
                del kwargs[key]

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
        ic('we\'re in business?', self.writer)

        global _converting
        if _converting:
            # NOTE _block.py calls us with empty args and empty kwargs ...
            ic('Help, we\'re already converting?')
            return func(*args, **kwargs)  # skip
        else:
            # clean start
            sys.setprofile(None)

        from myhdl import _traceSignals
        if _traceSignals._tracing:
            ic('Help, we\'re tracing Signals?')
            raise ConversionError("Cannot use Converter while tracing signals")

        _converting = 1
        if self.name is None:
            self.name = func.func.__name__

        try:
            h = _getHierarchy(self.name, func)
        finally:
            _converting = 0

        # start the output file
        self.writer.openfile(self.name, self.directory)

        ### initialize properly ###
        _genUniqueSuffix.reset()

        arglist = _flatten(self.writer.hdl, h.top)
        _checkArgs(arglist, self.writer.usercode)
        genlist = _analyzeGens(arglist, h.absnames)
        siglist, memlist = _analyzeSigs(h.hierarchy)
        # generic annotate for 'all' target HDLs
        _annotateTypes(genlist, self.writer.usercode)

        # infer interface after signals have been analyzed
        func._inferInterface()
        intf = func
        intf.name = self.name

        # self._convert_filter(h, intf, doc, siglist, memlist, genlist)

        # all this gets delegated to the respective writer
        self.writer.writeFileHeader()
        self.writer.writeModuleHeader(intf)
        self.writer.writeSigDecls(intf, siglist, memlist)
        # converting the generators is done here in a generic way
        # we will call on the hdl.write to translate the 'intermediate' representation
        # into the correct appropriate HDL construct
        self._convertGens(genlist)

        # almost done
        self.writer.writeModuleFooter()

        # build portmap for cosimulation
        portmap = {}
        for n, s in intf.argdict.items():
            if hasattr(s, 'driver'):
                portmap[n] = s.driver()
            else:
                portmap[n] = s
        self.portmap = portmap

        ### clean-up properly ###
        self._cleanup(siglist, memlist)

        return h.top

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
        self.standard = '2001'
        self.prefer_blocking_assignments = True
        self.radix = ''
        self.header = ""
        self.no_myhdl_header = False
        self.no_testbench = False
        self.trace = False

    def _convertGens(self, genlist):
        blockBuf = StringIO()
        funcBuf = StringIO()
        for tree in genlist:
            if isinstance(tree, self.writer.usercode):
                blockBuf.write(str(tree))
                continue

            if tree.kind == _kind.ALWAYS:
                Visitor = _ConvertAlwaysVisitor
            elif tree.kind == _kind.INITIAL:
                Visitor = _ConvertInitialVisitor
            elif tree.kind == _kind.SIMPLE_ALWAYS_COMB:
                Visitor = _ConvertSimpleAlwaysCombVisitor
            elif tree.kind == _kind.ALWAYS_DECO:
                Visitor = _ConvertAlwaysDecoVisitor
            elif tree.kind == _kind.ALWAYS_SEQ:
                Visitor = _ConvertAlwaysSeqVisitor
            else:  # ALWAYS_COMB
                Visitor = _ConvertAlwaysCombVisitor
            v = Visitor(tree, blockBuf, funcBuf, self.writer)
            v.visit(tree)
        self.writer.file.write(funcBuf.getvalue())
        funcBuf.close()
        self.writer.file.write(blockBuf.getvalue())
        blockBuf.close()


opmap = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.Div: '/',
    ast.Mod: '%',
    ast.Pow: '**',
    ast.LShift: '<<',
    ast.RShift: '>>>',
    ast.BitOr: '|',
    ast.BitAnd: '&',
    ast.BitXor: '^',
    ast.FloorDiv: '/',
    ast.Invert: '~',
    ast.Not: '!',
    ast.UAdd: '+',
    ast.USub: '-',
    ast.Eq: '==',
    ast.Gt: '>',
    ast.GtE: '>=',
    ast.Lt: '<',
    ast.LtE: '<=',
    ast.NotEq: '!=',
    ast.And: '&&',
    ast.Or: '||',
}

nameconstant_map = {
    True: "1'b1",
    False: "1'b0",
    None: "'bz"
}


class _ConvertVisitor(ast.NodeVisitor, _ConversionMixin):

    def __init__(self, tree, buf, writer):
        self.tree = tree
        self.buf = buf
        self.returnLabel = tree.name
        self.ind = ''
        self.isSigAss = False
        self.okSigAss = True
        self.labelStack = []
        self.context = _context.UNKNOWN
        self.writer = writer

    def raiseError(self, node, kind, msg=""):
        lineno = self.getLineNo(node)
        info = "in file %s, line %s:\n    " % \
            (self.tree.sourcefile, self.tree.lineoffset + lineno)
        raise ConversionError(kind, msg, info)

    def write(self, arg):
        self.buf.write("%s" % arg)

    def writeline(self, nr=1):
        for __ in range(nr):
            self.buf.write("\n%s" % self.ind)

    # def writeDoc(self, node):
    #     assert hasattr(node, 'doc')
    #     doc = _makeDoc(node.doc, '// ', self.ind)
    #     self.write(doc)
    #     self.writeline()

    def indent(self):
        self.ind += ' ' * 4

    def dedent(self):
        self.ind = self.ind[:-4]

    def IntRepr(self, n, radix=''):
        return _intRepr(n, radix)

    def writeDeclaration(self, obj, name, direction):
        if direction:
            direction = direction + ' '
        if type(obj) is bool:
            self.write("%s%s" % (direction, name))
        elif isinstance(obj, int):
            if direction == "input ":
                self.write("input %s;" % name)
                self.writeline()
            self.write("integer %s" % name)
        elif isinstance(obj, _Ram):
            self.write("reg [%s-1:0] %s [0:%s-1]" % (obj.elObj._nrbits, name, obj.depth))
        elif hasattr(obj, '_nrbits'):
            s = ""
            if isinstance(obj, (intbv, _Signal)):
                if obj._min is not None and obj._min < 0:
                    s = "signed "
            self.write("%s%s[%s-1:0] %s" % (direction, s, obj._nrbits, name))
        else:
            raise AssertionError("var %s has unexpected type %s" % (name, type(obj)))
        # initialize regs
        # if direction == 'reg ' and not isinstance(obj, _Ram):
        # disable for cver
        if False:
            if isinstance(obj, EnumItemType):
                inival = obj._toVerilog()
            else:
                inival = int(obj)
            self.write(" = %s;" % inival)
        else:
            self.write(";")

    # def writeDeclarations(self):
    #     for name, obj in self.tree.vardict.items():
    #         self.writeline()
    #         self.writeDeclaration(obj, name, "reg")

    # def writeAlwaysHeader(self):
    #     assert self.tree.senslist
    #     senslist = self.tree.senslist
    #     self.write("always ")
    #     self.writeSensitivityList(senslist)
    #     self.write(" begin: %s" % self.tree.name)
    #     self.indent()

    # def writeSensitivityList(self, senslist):
    #     ic(self.__class__.__name__, senslist)
    #     sep = ', '
    #     if toVerilog.standard == '1995':
    #         sep = ' or '
    #     self.write("@(")
    #     for e in senslist[:-1]:
    #         self.write(e._toVerilog())
    #         self.write(sep)
    #     self.write(senslist[-1]._toVerilog())
    #     self.write(")")

    def visit_BinOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if isinstance(node.op, ast.Mod) and self.context == _context.PRINT:
            self.visit(node.left)
            self.write(", ")
            self.visit(node.right)
        else:
            if isinstance(node.op, ast.RShift):
                # Additional cast to signed of the full expression
                # this is apparently required by cver - not sure if it
                # is actually required by standard Verilog.
                # It shouldn't hurt however.
                if node.signed:
                    self.write("$signed")

            self.context = None
            if node.signed:
                self.context = _context.SIGNED
            self.write("(")
            ic(self.writer.ir.append('('))
            self.visit(node.left)
            ic(self.writer.ir.append(node.op))
            self.write(" %s " % opmap[type(node.op)])
            self.visit(node.right)
            self.write(")")
            ic(self.writer.ir.append(')'))
            self.context = None

    def checkOpWithNegIntbv(self, node, op):
        if op in ("+", "-", "*", "~", "&&", "||", "!"):
            return
        if isinstance(node, ast.Name):
            o = node.obj
            if isinstance(o, (_Signal, intbv)) and o.min is not None and o.min < 0:
                self.raiseError(node, _error.NotSupported,
                                "negative intbv with operator %s" % op)

    def visit_BoolOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("(")
        ic(self.writer.ir.append('('))
        self.visit(node.values[0])
        for n in node.values[1:]:
            self.write(" %s " % opmap[type(node.op)])
            ic(self.writer.ir.append(node.op))
            self.visit(n)
        self.write(")")
        ic(self.writer.ir.append(')'))

    def visit_UnaryOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("(%s" % opmap[type(node.op)])
        ic(self.writer.ir.extend(['(', node.op]))
        self.visit(node.operand)
        self.write(")")
        ic(self.writer.ir.append(')'))

    def visit_Attribute(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if isinstance(node.ctx, ast.Store):
            self.setAttr(node)
        else:
            self.getAttr(node)

    def setAttr(self, node):
        assert node.attr == 'next'
        self.isSigAss = self.okSigAss
        self.visit(node.value)

    def getAttr(self, node):
        if isinstance(node.value, ast.Subscript):
            self.setAttr(node)
            return

        assert isinstance(node.value, ast.Name), node.value
        n = node.value.id
        if n in self.tree.symdict:
            obj = self.tree.symdict[n]
        elif n in self.tree.vardict:
            obj = self.tree.vardict[n]
        else:
            raise AssertionError("object not found")
        if isinstance(obj, _Signal):
            if node.attr == 'next':
                self.isSigAss = self.okSigAss
                self.visit(node.value)
            elif node.attr in ('posedge', 'negedge'):
                self.write(node.attr)
                self.write(' ')
                self.visit(node.value)
            elif node.attr == 'val':
                self.visit(node.value)
        if isinstance(obj, (_Signal, intbv)):
            if node.attr in ('min', 'max'):
                self.write("%s" % node.obj)
        if isinstance(obj, EnumType):
            assert hasattr(obj, node.attr)
            e = getattr(obj, node.attr)
            self.write(e._toVerilog())

    def visit_Assert(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("if (")
        self.visit(node.test)
        self.write(" !== 1) begin")
        self.indent()
        self.writeline()
        self.write('$display("*** AssertionError ***");')
        # self.writeline()
        # self.write('$finish;')
        self.dedent()
        self.writeline()
        self.write("end")

    def visit_Assign(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # shortcut for expansion of ROM in case statement
        if isinstance(node.value, ast.Subscript) and \
                      not isinstance(node.value.slice, ast.Slice) and \
                      isinstance(node.value.value.obj, _Rom):
            rom = node.value.value.obj.rom
#            self.write("// synthesis parallel_case full_case")
#            self.writeline()
            self.write("case (")
            self.visit(node.value.slice)
            self.write(")")
            self.indent()
            for i, n in enumerate(rom):
                self.writeline()
                if i == len(rom) - 1:
                    self.write("default: ")
                else:
                    self.write("%s: " % i)
                self.visit(node.targets[0])
                if self.isSigAss:
                    self.write(' <= ')
                    self.isSigAss = False
                else:
                    self.write(' = ')
                s = self.IntRepr(n)
                self.write("%s;" % s)
            self.dedent()
            self.writeline()
            self.write("endcase")

        elif isinstance(node.value, ast.ListComp):
            # skip list comprehension assigns for now
            pass

        else:
            # default behavior
            # there should only be a single target
            ic(self.writer.ir.append('assign1'))
            self.visit(node.targets[0])
            ic(self.writer.ir.append(self.isSigAss))
            if self.isSigAss:
                self.write(' <= ')
                self.isSigAss = False
            else:
                self.write(' = ')
            self.visit(node.value)
            self.write(';')
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]

    def visit_AugAssign(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # XXX apparently no signed context required for augmented assigns
        ic(self.writer.ir.append('augassign'))
        self.visit(node.target)
        self.write(" = ")
        self.visit(node.target)
        self.write(" %s " % opmap[type(node.op)])
        ic(self.writer.ir.append(node.op))
        self.visit(node.value)
        self.write(";")
        self.writer.emitline()
        # ic(self.writer.ir)
        # del self.writer.ir[:]

    def visit_Break(self, node,):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("disable %s;" % self.labelStack[-2])
        ic(self.writer.ir.append('break'))
        self.writer.emitline()
        # ic(self.writer.ir)
        # del self.writer.ir[:]

    def visit_Call(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.context = None
        fn = node.func
        # assert isinstance(fn, astNode.Name)
        f = self.getObj(fn)

        if f is print:
            self.visit_Print(node)
            return

        opening, closing = '(', ')'
        if f is bool:
            self.write("(")
            self.visit(node.args[0])
            self.write(" != 0)")
            # self.write(" ? 1'b1 : 1'b0)")
            return
        elif f is len:
            val = self.getVal(node)
            self.require(node, val is not None, "cannot calculate len")
            self.write(repr(val))
            return
        elif f is now:
            self.write("$time")
            return
        elif f is ord:
            opening, closing = '', ''
            node.args[0].s = str(ord(node.args[0].s))
        elif f is int:
            opening, closing = '', ''
            # convert number argument to integer
            if sys.version_info >= (3, 8, 0):
                if isinstance(node.args[0], ast.Constant):
                    node.args[0].n = int(node.args[0].n)
            else:
                if isinstance(node.args[0], ast.Num):
                    node.args[0].n = int(node.args[0].n)
        elif f in (intbv, modbv):
            self.visit(node.args[0])
            return
        elif f == intbv.signed:  # note equality comparison
            # comes from a getattr
            opening, closing = '', ''
            if not fn.value.signed:
                opening, closing = "$signed(", ")"
            self.write(opening)
            self.visit(fn.value)
            self.write(closing)
        elif (type(f) in (type,)) and issubclass(f, Exception):
            self.write(f.__name__)
        elif f in (posedge, negedge):
            opening, closing = ' ', ''
            self.write(f.__name__)
        elif f is concat:
            opening, closing = '{', '}'
        elif f is delay:
            self.visit(node.args[0])
            return
        elif hasattr(node, 'tree'):
            self.write(node.tree.name)
        else:
            self.write(f.__name__)
        if node.args:
            self.write(opening)
            self.visit(node.args[0])
            for arg in node.args[1:]:
                self.write(", ")
                self.visit(arg)
            self.write(closing)
        if hasattr(node, 'tree'):
            if node.tree.kind == _kind.TASK:
                Visitor = _ConvertTaskVisitor
            else:
                Visitor = _ConvertFunctionVisitor
            v = Visitor(node.tree, self.funcBuf)
            v.visit(node.tree)

    def visit_Compare(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.context = None
        if node.signed:
            self.context = _context.SIGNED
        self.write("(")
        self.visit(node.left)
        self.write(" %s " % opmap[type(node.ops[0])])
        self.visit(node.comparators[0])
        self.write(")")
        self.context = None

    if sys.version_info >= (3, 9, 0):

        def visit_Constant(self, node):
            ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
            ic(self.writer.ir.append(node.value))
            if node.value is None:
                # NameConstant
                self.write(nameconstant_map[node.obj])
            elif isinstance(node.value, bool):
                self.write(nameconstant_map[node.obj])
            elif isinstance(node.value, int):
                # Num
                if self.context == _context.PRINT:
                    self.write('"%s"' % node.value)
                else:
                    self.write(self.IntRepr(node.value))
            elif isinstance(node.value, str):
                # Str
                s = node.value
                if self.context == _context.PRINT:
                    self.write('"%s"' % s)
                elif len(s) == s.count('0') + s.count('1'):
                    self.write("%s'b%s" % (len(s), s))
                else:
                    self.write(s)

    else:

        def visit_Num(self, node):
            ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
            if self.context == _context.PRINT:
                self.write('"%s"' % node.n)
            else:
                self.write(self.IntRepr(node.n))

        def visit_Str(self, node):
            ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
            s = node.s
            if self.context == _context.PRINT:
                self.write('"%s"' % s)
            elif len(s) == s.count('0') + s.count('1'):
                self.write("%s'b%s" % (len(s), s))
            else:
                self.write(s)

        def visit_NameConstant(self, node):
            self.write(nameconstant_map[node.obj])

    def visit_Continue(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("disable %s;" % self.labelStack[-1])

    def visit_Expr(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        expr = node.value
        # docstrings on unofficial places
        if isinstance(expr, ast.Str):
            doc = _makeDoc(expr.s, '// ', self.ind)
            self.write(doc)
            return
        # skip extra semicolons
        if sys.version_info >= (3, 8, 0):
            if isinstance(expr, ast.Constant):
                return
        else:
            if isinstance(expr, ast.Num):
                return
        self.visit(expr)
        # ugly hack to detect an orphan "task" call
        if isinstance(expr, ast.Call) and hasattr(expr, 'tree'):
            self.write(';')

    def visit_IfExp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.visit(node.test)
        self.write(' ? ')
        self.visit(node.body)
        self.write(' : ')
        self.visit(node.orelse)

    def visit_For(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.labelStack.append(node.breakLabel)
        self.labelStack.append(node.loopLabel)
        var = node.target.id
        cf = node.iter
        f = self.getObj(cf.func)
        args = cf.args
        assert len(args) <= 3
        if f is range:
            cmp = '<'
            op = '+'
            oneoff = ''
            if len(args) == 1:
                start, stop, step = None, args[0], None
            elif len(args) == 2:
                start, stop, step = args[0], args[1], None
            else:
                start, stop, step = args
        else:  # downrange
            cmp = '>='
            op = '-'
            oneoff = '-1'
            if len(args) == 1:
                start, stop, step = args[0], None, None
            elif len(args) == 2:
                start, stop, step = args[0], args[1], None
            else:
                start, stop, step = args
        if node.breakLabel.isActive:
            self.write("begin: %s" % node.breakLabel)
            self.writeline()
        self.write("for (%s=" % var)
        ic(self.writer.ir.extend(['for', '[', var]))
        if start is None:
            self.write("0")
            ic(self.writer.ir.append(0))
        else:
            self.visit(start)
        self.write("%s; %s%s" % (oneoff, var, cmp))
        if stop is None:
            self.write("0")
        else:
            self.visit(stop)
        self.write("; %s=%s%s" % (var, var, op))
        if step is None:
            self.write("1")
        else:
            v = self.getVal(step)
            self.require(node, v >= 0, "step should be >= 0")
            self.visit(step)
        self.write(") begin")
        ic(self.writer.ir.append(']'))
        if node.loopLabel.isActive:
            self.write(": %s" % node.loopLabel)
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        if node.breakLabel.isActive:
            self.writeline()
            self.write("end")
        self.labelStack.pop()
        self.labelStack.pop()

    def visit_FunctionDef(self, node):
        raise AssertionError("To be implemented in subclass")

    def visit_If(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if node.ignore:
            return
        if node.isCase:
            self.mapToCase(node)
        else:
            self.mapToIf(node)

    def visit_Match(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("case (")
        self.visit(node.subject)
        self.write(")")
        self.indent()
        for case in node.cases:
            self.visit(case)
            self.writeline()

        self.dedent()
        self.writeline()
        self.write("endcase")

    def visit_match_case(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        pattern = node.pattern
        self.visit(pattern)

        self.write(": begin ")
        self.indent()
        # Write all the multiple assignment per case
        for stmt in node.body:
            self.writeline()
            self.visit(stmt)
        self.dedent()
        self.writeline()
        self.write("end")

    def visit_MatchValue(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        item = node.value
        obj = self.getObj(item)

        if isinstance(obj, EnumItemType):
            itemRepr = obj._toVerilog()
        else:
            itemRepr = self.IntRepr(item.value, radix='hex')

        self.write(itemRepr)

    def visit_MatchSingleton(self, node):
        raise AssertionError("Unsupported Match type %s " % (type(node)))

    def visit_MatchSequence(self, node):
        raise AssertionError("Unsupported Match type %s " % (type(node)))

    def visit_MatchStar(self, node):
        raise AssertionError("Unsupported Match type %s " % (type(node)))

    def visit_MatchMapping(self, node):
        raise AssertionError("Unsupported Match type %s " % (type(node)))

    def visit_MatchClass(self, node):
        for pattern in node.patterns:
            self.visit(pattern)

    def visit_MatchAs(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if node.name is None and  node.pattern is None:
            self.write("default")
        else:
            raise AssertionError("Unknown name %s or pattern %s" % (node.name, node.pattern))

    def visit_MatchOr(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        for i, pattern in enumerate(node.patterns):
            self.visit(pattern)
            if not i == len(node.patterns) - 1:
                self.write(" | ")

    def mapToCase(self, node, *args):
        var = node.caseVar
#        self.write("// synthesis parallel_case")
#        if node.isFullCase:
#            self.write(" full_case")
#        self.writeline()
        self.write("case (")
        ic(self.writer.ir.append('case'))
        self.visit(var)
        self.write(")")
        self.writer.emitline()
        # ic(self.writer.ir)
        # del self.writer.ir[:]
        self.indent()
        for test, suite in node.tests:
            self.writeline()
            item = test.case[1]
            ic(self.writer.ir.extend(['when', item]))
            if isinstance(item, EnumItemType):
                self.write(item._toVerilog())
            else:
                self.write(self.IntRepr(item, radix='hex'))
            self.write(": begin")
            ic(self.writer.ir.append('begin'))
            self.indent()
            self.visit_stmt(suite)
            self.dedent()
            self.writeline()
            self.write("end")
            ic(self.writer.ir.append('end'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]
        if node.else_:
            self.writeline()
            self.write("default: begin")
            ic(self.writer.ir.append('default'))
            self.indent()
            self.visit_stmt(node.else_)
            self.dedent()
            self.writeline()
            self.write("end")
            ic(self.writer.ir.append('end'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]
        self.dedent()
        self.writeline()
        self.write("endcase")
        ic(self.writer.ir.append('end case'))
        self.writer.emitline()
        # ic(self.writer.ir)
        # del self.writer.ir[:]

    def mapToIf(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        first = True
        for test, suite in node.tests:
            if first:
                ifstring = "if ("
                ic(self.writer.ir.append('if'))
                first = False
            else:
                ifstring = "else if ("
                ic(self.writer.ir.append('else if'))
                self.writeline()
            self.write(ifstring)
            self.visit(test)
            self.write(") begin")
            ic(self.writer.ir.append('begin'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]

            self.indent()
            self.visit_stmt(suite)
            self.dedent()
            self.writeline()
            self.write("end")
            ic(self.writer.ir.append('end'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]

        if node.else_:
            self.writeline()
            self.write("else begin")
            ic(self.writer.ir.append('else begin'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]
            self.indent()
            self.visit_stmt(node.else_)
            self.dedent()
            self.writeline()
            self.write("end")
            ic(self.writer.ir.append('end'))
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]

        # final closing end
        ic(self.writer.ir.append('end if'))
        self.writer.emitline()
        # ic(self.writer.ir)
        # del self.writer.ir[:]

    def visitKeyword(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.visit(node.expr)

    def visit_Module(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        for stmt in node.body:
            self.visit(stmt)

    def visit_ListComp(self, node):
        # do nothing
        pass

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.setName(node)
        else:
            self.getName(node)

    def setName(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write(node.id)

    def getName(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        n = node.id
        ic(self.writer.ir.append(n))
        addSignBit = False
        isMixedExpr = (not node.signed) and (self.context == _context.SIGNED)
        if n in self.tree.vardict:
            addSignBit = isMixedExpr
            s = n
        elif n in self.tree.argnames:
            assert n in self.tree.symdict
            addSignBit = isMixedExpr
            s = n
        elif n in self.tree.symdict:
            obj = self.tree.symdict[n]
            if isinstance(obj, bool):
                s = "1'b%s" % int(obj)
            elif isinstance(obj, int):
                s = self.IntRepr(obj)
            elif isinstance(obj, tuple):  # Python3.9+ ast.Index replacement serves a tuple
                s = n
            elif isinstance(obj, _Signal):
                addSignBit = isMixedExpr
                s = str(obj)
            elif _isMem(obj):
                m = _getMemInfo(obj)
                assert m.name
                s = m.name
            elif isinstance(obj, EnumItemType):
                s = obj._toVerilog()
            elif (type(obj) in (type,)) and issubclass(obj, Exception):
                s = n
            else:
                self.raiseError(node, _error.UnsupportedType, "%s, %s %s" % (n, type(obj), obj))
        else:
            raise AssertionError("name ref: %s" % n)

        if addSignBit:
            self.write("$signed({1'b0, ")

        if s.startswith('--'):
            self.write(s.replace('--', '//'))
        else:
            self.write(s)
        if addSignBit:
            self.write("})")

    def visit_Pass(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("// pass")

    def visit_Print(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        argnr = 0
        for s in node.format:
            if isinstance(s, str):
                self.write('$write("%s");' % s)
            else:
                a = node.args[argnr]
                argnr += 1
                obj = a.obj
                if s.conv is int or isinstance(obj, int):
                    fs = "%0d"
                else:
                    fs = "%h"
                self.context = _context.PRINT
                if isinstance(obj, str):
                    self.write('$write(')
                    self.visit(a)
                    self.write(');')
                elif (s.conv is str) and isinstance(obj, bool):
                    self.write('if (')
                    self.visit(a)
                    self.write(')')
                    self.writeline()
                    self.write('    $write("True");')
                    self.writeline()
                    self.write('else')
                    self.writeline()
                    self.write('    $write("False");')
                elif isinstance(obj, EnumItemType):
                    tipe = obj._type
                    self.write('case (')
                    self.visit(a)
                    self.write(')')
                    self.indent()
                    for n in tipe._names:
                        self.writeline()
                        item = getattr(tipe, n)
                        self.write("'b%s: " % item._val)
                        self.write('$write("%s");' % n)
                    self.dedent()
                    self.writeline()
                    self.write("endcase")
                else:
                    self.write('$write("%s", ' % fs)
                    self.visit(a)
                    self.write(');')
                self.context = _context.UNKNOWN
            self.writeline()
        self.write('$write("\\n");')

    def visit_Raise(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        self.write("$finish;")

    def visit_Return(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        self.write("disable %s;" % self.returnLabel)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            self.accessSlice(node)
        else:
            self.accessIndex(node)

    def accessSlice(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        if isinstance(node.value, ast.Call) and \
           node.value.func.obj in (intbv, modbv) and \
           _isConstant(node.value.args[0], self.tree.symdict):
            c = self.getVal(node)
            self.write("%s'h" % c._nrbits)
            self.write("%x" % c._val)
            return

        addSignBit = isinstance(node.ctx, ast.Load) and (self.context == _context.SIGNED)
        if addSignBit:
            self.write("$signed({1'b0, ")
        self.context = None
        self.visit(node.value)
        lower, upper = node.slice.lower, node.slice.upper
        # special shortcut case for [:] slice
        if lower is None and upper is None:
            return

        if isinstance(lower, ast.BinOp) and isinstance(lower.left, ast.Name) and isinstance(upper, ast.Name) and upper.id == lower.left.id and isinstance(lower.op, ast.Add):
            self.write("[")
            self.visit(upper)
            self.write("+:")
            self.visit(lower.right)
            self.write("]")
            return

        self.write("[")
        ic(self.writer.ir.extend(['Slice', '[']))
        if lower is None:
            self.write("%s" % node.obj._nrbits)
            ic(self.writer.ir.append(None))
        else:
            self.visit(lower)

        self.write("-1:")
        if upper is None:
            self.write("0")
            ic(self.writer.ir.append('0'))
        else:
            self.visit(upper)

        self.write("]")
        if addSignBit:
            self.write("})")
        ic(self.writer.ir.append(']'))

    def accessIndex(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        addSignBit = isinstance(node.ctx, ast.Load) and \
            (not node.signed) and \
            (self.context == _context.SIGNED)
        if addSignBit:
            self.write("$signed({1'b0, ")
        self.context = None
        self.visit(node.value)
        self.write("[")
        ic(self.writer.ir.extend(['Index', '[']))
        # assert len(node.subs) == 1
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: no ast.Index wrapper
            self.visit(node.slice)
        else:
            self.visit(node.slice.value)
        self.write("]")
        if addSignBit:
            self.write("})")
        ic(self.writer.ir.append(']'))

    def visit_stmt(self, body):
        # 'body' is a list of statements
        ic(self.__class__.__name__, body, pp.pformat(vars(self)))
        for stmt in body:
            ic(self.__class__.__name__, astdump(stmt, show_offsets=False), pp.pformat(vars(stmt)))
            self.writeline()
            self.visit(stmt)
            # ugly hack to detect an orphan "task" call
            if isinstance(stmt, ast.Call) and hasattr(stmt, 'tree'):
                self.write(';')

    def visit_Tuple(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        assert self.context != None
        sep = ", "
        tpl = node.elts
        self.visit(tpl[0])
        for elt in tpl[1:]:
            self.write(sep)
            self.visit(elt)

    def visit_While(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        self.labelStack.append(node.breakLabel)
        self.labelStack.append(node.loopLabel)
        if node.breakLabel.isActive:
            self.write("begin: %s" % node.breakLabel)
            self.writeline()
        self.write("while (")
        self.visit(node.test)
        self.write(") begin")
        if node.loopLabel.isActive:
            self.write(": %s" % node.loopLabel)
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        if node.breakLabel.isActive:
            self.writeline()
            self.write("end")
        self.labelStack.pop()
        self.labelStack.pop()

    def visit_Yield(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        yieldObj = self.getObj(node.value)
        assert node.senslist
        senslist = node.senslist
        if isinstance(yieldObj, delay):
            self.write("# ")
            self.context = _context.YIELD
            self.visit(node.value)
            self.context = _context.UNKNOWN
            self.write(";")
        else:
            self.writeSensitivityList(senslist)
            self.write(";")


class _ConvertAlwaysVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.writer.writeDoc(node)
        w = node.body[-1]
        y = w.body[0]
        if isinstance(y, ast.Expr):
            y = y.value
        assert isinstance(y, ast.Yield)
        self.writer.writeAlwaysHeader(self.tree)
        self.writeDeclarations(self.tree)
        # assert isinstance(w.body, astNode.Stmt)
        for stmt in w.body[1:]:
            self.writeline()
            self.visit(stmt)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertInitialVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.writer.writeDoc(node)
        self.write("initial begin: %s" % self.tree.name)
        self.indent()
        self.writeDeclarations(self.tree)
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertAlwaysCombVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        if toVerilog.prefer_blocking_assignments:
            self.okSigAss = False
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self)))
        self.writer.writeDoc(node)
        self.writer.writeAlwaysHeader(self.tree)
        self.writer.writeDeclarations(self.tree)
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertSimpleAlwaysCombVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_Attribute(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if isinstance(node.ctx, ast.Store):
            # try intercepting '-- OpenPort' signals
            if isinstance(node.value, ast.Name):
                obj = self.tree.symdict[node.value.id]
                if obj._name.startswith('-- OpenPort'):
                    self.write('// ')

            self.write("assign ")
            ic(self.writer.ir.append('assign2'))
            self.visit(node.value)
        else:
            self.getAttr(node)

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.writer.writeDoc(node)
        self.visit_stmt(node.body)
        self.writeline(2)


class _ConvertAlwaysDecoVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.writer.writeDoc(node)
        self.writer.writeAlwaysHeader(self.tree)
        self.writer.writeDeclarations(self.tree)
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


def _convertInitVal(reg, init):
    if isinstance(reg, _Signal):
        tipe = reg._type
    else:
        assert isinstance(reg, intbv)
        tipe = intbv
    if tipe is bool:
        v = '1' if init else '0'
    elif tipe is intbv:
        init = int(init)  # int representation
        v = "%s" % init if init is not None else "'bz"
    else:
        assert isinstance(init, EnumItemType)
        v = init._toVerilog()
    return v


class _ConvertAlwaysSeqVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)), pp.pformat(vars(self.tree)))
        self.writer.writeDoc(node)
        self.writer.writeAlwaysHeader(self.tree)
        self.writer.writeDeclarations(self.tree)
        reset = self.tree.reset
        sigregs = self.tree.sigregs
        varregs = self.tree.varregs
        if reset is not None:
            self.writeline()
            self.write("if (%s == %s) begin" % (reset, int(reset.active)))
            self.indent()
            for s in sigregs:
                self.writeline()
                self.write("%s <= %s;" % (s, _convertInitVal(s, s._init)))
            for v in varregs:
                n, reg, init = v
                self.writeline()
                self.write("%s = %s;" % (n, _convertInitVal(reg, init)))
            self.dedent()
            self.writeline()
            self.write("end")
            self.writeline()
            self.write("else begin")
            self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        if reset is not None:
            self.writeline()
            self.write("end")
            self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertFunctionVisitor(_ConvertVisitor):

    def __init__(self, tree, funcBuf):
        _ConvertVisitor.__init__(self, tree, funcBuf)
        self.returnObj = tree.returnObj
        self.returnLabel = _Label("RETURN")

    def writeOutputDeclaration(self):
        obj = self.tree.returnObj
        self.writeDeclaration(obj, self.tree.name, direction='')

    def writeInputDeclarations(self):
        for name in self.tree.argnames:
            obj = self.tree.symdict[name]
            self.writeline()
            self.writeDeclaration(obj, name, "input")

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("function ")
        self.writeOutputDeclaration()
        self.indent()
        self.writeInputDeclarations()
        self.writer.writeDeclarations(self.tree)
        self.dedent()
        self.writeline()
        self.write("begin: %s" % self.returnLabel)
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline()
        self.write("endfunction")
        self.writeline(2)

    def visit_Return(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("%s = " % self.tree.name)
        self.visit(node.value)
        self.write(";")
        self.writeline()
        self.write("disable %s;" % self.returnLabel)


class _ConvertTaskVisitor(_ConvertVisitor):

    def __init__(self, tree, funcBuf):
        _ConvertVisitor.__init__(self, tree, funcBuf)
        self.returnLabel = _Label("RETURN")

    def writeInterfaceDeclarations(self):
        for name in self.tree.argnames:
            obj = self.tree.symdict[name]
            isoutput = name in self.tree.outputs
            isinput = name in self.tree.inputs
            isinout = isinput and isoutput
            direction = (isinout and "inout") or (isoutput and "output") or "input"
            self.writeline()
            self.writeDeclaration(obj, name, direction)

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.write("task %s;" % self.tree.name)
        self.indent()
        self.writeInterfaceDeclarations()
        self.writer.writeDeclarations(self.tree)
        self.dedent()
        self.writeline()
        self.write("begin: %s" % self.returnLabel)
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline()
        self.write("endtask")
        self.writeline(2)


def _maybeNegative(obj):
    if hasattr(obj, '_min') and (obj._min is not None) and (obj._min < 0):
        return True
    if isinstance(obj, int) and obj < 0:
        return True
    return False


class _AnnotateTypesVisitor(ast.NodeVisitor, _ConversionMixin):

    def __init__(self, tree):
        self.tree = tree

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # don't visit arguments and decorators
        for stmt in node.body:
            ic(self.__class__.__name__, astdump(stmt, show_offsets=False))
            self.visit(stmt)

    def visit_Attribute(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        if isinstance(node.ctx, ast.Store):
            # self.setAttr(node)
            # self.visit(node.value)
            pass
        else:
            # self.getAttr(node)
            node.signed = False
        self.visit(node.value)

    # def setAttr(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
    #     self.visit(node.value)
    #
    # def getAttr(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False))
    #     node.signed = False
    #     self.visit(node.value)

    def visit_Assert(self, node):
        self.visit(node.test)

    def visit_AugAssign(self, node):
        self.visit(node.target)
        self.visit(node.value)
        # if isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor)):
        #     node.value.vhd = copy(node.target.vhd)
        #     node.vhdOri = copy(node.target.vhd)
        # elif isinstance(node.op, (ast.RShift, ast.LShift)):
        #     node.value.vhd = vhd_int()
        #     node.vhdOri = copy(node.target.vhd)
        # else:
        #     node.left, node.right = node.target, node.value
        #     self.inferBinOpType(node)
        # node.vhd = copy(node.target.vhd)

    def visit_BinOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        self.visit(node.left)
        self.visit(node.right)
        node.signed = node.left.signed or node.right.signed
        # special treatement of subtraction unless in a top-level rhs
        if isinstance(node.op, ast.Sub) and not hasattr(node, 'isRhs'):
            node.signed = True

    # VHDL
    # def visit_BinOp(self, node):
    #     self.generic_visit(node)
    #     if isinstance(node.op, (ast.LShift, ast.RShift)):
    #         self.inferShiftType(node)
    #     elif isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
    #         self.inferBitOpType(node)
    #     elif isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Str):  # format string
    #         pass
    #     else:
    #         self.inferBinOpType(node)

    def visit_BoolOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        for n in node.values:
            self.visit(n)
        node.signed = False

    def visit_UnaryOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        self.visit(node.operand)
        node.signed = node.operand.signed
        if isinstance(node.op, ast.USub):
            node.obj = int(-1)
            if sys.version_info >= (3, 8, 0):
                if isinstance(node.operand, ast.Constant):
                    node.signed = True
            else:
                if isinstance(node.operand, ast.Num):
                    node.signed = True

    def visit_Call(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        node.signed = False
        # for n in ast.iter_child_nodes(node):
        for n in [node.left] + node.comparators:
            self.visit(n)
            if n.signed:
                node.signed = True

    def visit_For(self, node):
        var = node.target.id
        # make it possible to detect loop variable
        self.tree.vardict[var] = _loopInt(-1)
        self.generic_visit(node)

    def visit_If(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        if node.ignore:
            return
        self.generic_visit(node)
        # for test, suite in node.tests:
        #     test.vhd = vhd_boolean()

    def visit_IfExp(self, node):
        self.generic_visit(node)

    if sys.version_info >= (3, 9, 0):

        def visit_Constant(self, node):
            ic(self.__class__.__name__, astdump(node, show_offsets=False))
            node.signed = False

    else:

        def visit_Num(self, node):
            node.signed = False

        def visit_Str(self, node):
            node.signed = False

        def visit_NameConstant(self, node):
            node.signed = False

    def visit_Name(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        if node.id in self.tree.vardict:
            node.obj = self.tree.vardict[node.id]
        if isinstance(node.ctx, ast.Store):
            # self.setName(node)
            pass
        else:
            # self.getName(node)
            node.signed = _maybeNegative(node.obj)

    # def setName(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False))
    #     pass
    #
    # def getName(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False))
    #     node.signed = _maybeNegative(node.obj)

    def visit_Subscript(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        if isinstance(node.slice, ast.Slice):
            self.accessSlice(node)
        else:
            self.accessIndex(node)

    def accessSlice(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        node.signed = False
        self.generic_visit(node)

    def accessIndex(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        node.signed = _maybeNegative(node.obj)
        self.generic_visit(node)

    def visit_Tuple(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False))
        node.signed = False
        self.generic_visit(node)


def _annotateTypes(genlist, usercode):
    for tree in genlist:
        if isinstance(tree, usercode):
            continue
        v = _AnnotateTypesVisitor(tree)
        v.visit(tree)


class _loopInt(int):
    pass


def _intRepr(n, radix=''):
    # write size for large integers (beyond 32 bits signed)
    # with some safety margin
    # XXX signed indication 's' ???
    p = abs(n)
    size = ''
    num = str(p).rstrip('L')
    if radix == "hex" or p >= 2 ** 30:
        radix = "'h"
        num = hex(p)[2:].rstrip('L')
    if p >= 2 ** 30:
        size = int(math.ceil(math.log(p + 1, 2))) + 1  # sign bit!
#            if not radix:
#                radix = "'d"
    r = "%s%s%s" % (size, radix, num)
    if n < 0:  # add brackets and sign on negative numbers
        r = "(-%s)" % r
    return r

# converter = _Converter()

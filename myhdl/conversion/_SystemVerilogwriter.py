'''
Created on 29 okt. 2023

@author: josy
'''

import sys
import os
import math
import textwrap
import inspect
import ast
import string
from io import StringIO
import warnings

from astpretty import pformat as astdump

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

from myhdl import  ConversionError
from myhdl import __version__ as myhdlversion
from myhdl import ToVerilogError, ToVerilogWarning
from myhdl._extractHierarchy import (_isMem, _getMemInfo)
from myhdl._Signal import  posedge, negedge
from myhdl._enum import EnumType
from myhdl._simulator import now
from myhdl._modbv import modbv
from myhdl._delay import delay
from myhdl._concat import concat
from myhdl._extractHierarchy import (_UserVerilogCode)
from myhdl._Signal import Constant, _Signal
from myhdl._intbv import intbv
from myhdl._enum import EnumItemType
from myhdl._ShadowSignal import _TristateSignal, _TristateDriver
from myhdl.conversion._misc import _error, _makeDoc, getutcdatetime
from myhdl.conversion._analyze import (_Ram, _Rom)
from myhdl.conversion._misc import (_kind, _context, _ConversionMixin,
                                    _Label, _isConstant)


class SystemVerilogWriter(object):
    __slots__ = ("timescale",
                 "standard",
                 "prefer_blocking_assignments",
                 "radix",
                 "header",
                 "no_myhdl_header",
                 "testbench",
                 "portmap",
                 "trace",
                 "initial_values",
                 "usercode",
                 "file",
                 "hdl",
                 "comment",
                 "directory",
                 "path",
                 "filename",
                 "ind",
                 "ConvertAlwaysVisitor",
                 "ConvertInitialVisitor",
                 "ConvertSimpleAlwaysCombVisitor",
                 "ConvertAlwaysDecoVisitor",
                 "ConvertAlwaysSeqVisitor",
                 "ConvertAlwaysCombVisitor"
                 )

    def __init__(self, **kwargs):
        self.hdl = 'systemverilog'
        self.comment = '// '
        self.timescale = "1ns/10ps"
        self.standard = '2005'
        self.prefer_blocking_assignments = True
        self.radix = ''
        self.header = ''
        self.no_myhdl_header = False
        self.testbench = True
        self.trace = False
        self.initial_values = False
        self.usercode = _UserVerilogCode
        self.ind = ''
        for key, value in kwargs.items():
            ic("{0} = {1}".format(key, value))
            if key in ['trace', 'initial_values']:
                setattr(self, key, value)

        self.ConvertAlwaysVisitor = _ConvertAlwaysVisitor
        self.ConvertInitialVisitor = _ConvertInitialVisitor
        self.ConvertSimpleAlwaysCombVisitor = _ConvertSimpleAlwaysCombVisitor
        self.ConvertAlwaysDecoVisitor = _ConvertAlwaysDecoVisitor
        self.ConvertAlwaysSeqVisitor = _ConvertAlwaysSeqVisitor
        self.ConvertAlwaysCombVisitor = _ConvertAlwaysCombVisitor

    def openfile(self, name, directory):
        self.directory = directory
        self.filename = name + ".sv"
        self.path = os.path.join(directory, self.filename)
        setattr(self, 'file', open(self.path, 'w'))

    def writePackages(self, directory):
        pass

    def writeFileHeader(self):
        vvars = dict(filename=self.filename,
                    version=myhdlversion,
                    date=getutcdatetime()
                    )
        if not self.no_myhdl_header:
            print(string.Template(myhdl_header).substitute(vvars), file=self.file)
        if self.header:
            print(string.Template(self.header).substitute(vvars), file=self.file)
        print(file=self.file)
        print("`timescale {}".format(self.timescale), file=self.file)
        print(file=self.file)

    def writeModuleHeader(self, intf):
        doc = _makeDoc(inspect.getdoc(intf), self.comment)
        print(doc, file=self.file)
        print("module {} (".format(intf.name), file=self.file)
        b = StringIO()
        # ANSI-style module declaration only
        for portname in intf.argnames:
            s = intf.argdict[portname]
            if s._name is None:
                raise ToVerilogError(_error.ShadowingSignal, portname)
            if s._inList:
                raise ToVerilogError(_error.PortInList, portname)
            s._name = portname
            r = _getRangeString(s)
            p = _getSignString(s)
            if s._driven:
                if isinstance(s, _TristateSignal):
                    d = 'inout'
                else:
                    d = 'output'
                print('    {} logic {} {} {},'.format(d, p, r, portname), file=b)

            else:
                print('    input {} {} {},'.format(p, r, portname), file=b)
                if not s._read:
                    warnings.warn("{}: {}".format(_error.UnusedPort, portname),
                                  category=ToVerilogWarning
                                  )

        print(b.getvalue()[:-2], file=self.file)
        b.close()
        print(");", file=self.file)
        print(file=self.file)

    def writeDecls(self, intf, siglist, memlist):
        # _writeSigDecls(self.file, intf, siglist, memlist)
        # def _writeSigDecls(f, intf, siglist, memlist):
        constwires = []
        for s in siglist:
            if not s._used:
                continue

            if s._name in intf.argnames:
                continue

            if s._name.startswith('-- OpenPort'):
                # do not write a signal declaration
                continue

            r = _getRangeString(s)
            p = _getSignString(s)
            if s._driven:
                if not s._read and not isinstance(s, _TristateDriver):
                    warnings.warn("{}: {}".format(_error.UnreadSignal, s._name),
                                  category=ToVerilogWarning
                                  )
                # k = 'wire'
                # if s._driven == 'reg':
                #     k = 'reg'
                # the following line implements initial value assignments
                # don't initial value "wire", inital assignment to a wire
                # equates to a continuous assignment [reference]
                if not self.initial_values or s._driven == 'wire':
                    print("    logic {}{}{};".format(p, r, s._name), file=self.file)
                else:
                    if isinstance(s._init, EnumItemType):
                        print("    logic {}{}{} = {};" %
                              (p, r, s._name, s._init._toVerilog()), file=self.file)
                    else:
                        print("    logic {}{}{} = {};" %
                              (p, r, s._name, _intRepr(s._init)), file=self.file)
            elif s._read:
                if isinstance(s, Constant):
                    c = int(s.val)
                    c_len = s._nrbits
                    c_str = "{}".format(c)
                    print("    localparam {}{} = {}'d{};".format(r, s._name, c_len, c_str), file=self.file)
                else:
                    # the original exception
                    # raise ToVerilogError(_error.UndrivenSignal, s._name)
                    # changed to a warning and a continuous assignment to a wire
                    warnings.warn("{}: {}".format(_error.UndrivenSignal, s._name),
                                  category=ToVerilogWarning
                                  )
                    constwires.append(s)
                    print("    logic {}{};".format(r, s._name), file=self.file)
        # print(file=self.file)
        for m in memlist:
            if not m._used:
                continue
            # infer attributes for the case of named signals in a list
            for s in m.mem:
                if not m._driven and s._driven:
                    m._driven = s._driven
                if not m._read and s._read:
                    m._read = s._read
            if not m._driven and not m._read:
                continue
            r = _getRangeString(m.elObj)
            p = _getSignString(m.elObj)
            # k = 'wire'
            initial_assignments = None
            if m._driven:
                # k = m._driven

                if self.initial_values and not m._driven == 'wire':
                    if all([each._init == m.mem[0]._init for each in m.mem]):

                        initialize_block_name = ('INITIALIZE_' + m.name).upper()
                        _initial_assignments = (
                            '''
                            initial begin: {}
                                integer i;
                                for(i=0; i<%d; i=i+1) begin
                                    {}[i] = {};
                                end
                            end
                            ''' % (initialize_block_name, len(m.mem), m.name,
                                   _intRepr(m.mem[0]._init)))

                        initial_assignments = (
                            textwrap.dedent(_initial_assignments))

                    else:
                        val_assignments = '\n'.join(
                            ['    {}[%d] <= {};' %
                             (m.name, n, _intRepr(each._init))
                             for n, each in enumerate(m.mem)])
                        initial_assignments = (
                            'initial begin\n' + val_assignments + '\nend')
                print("logic {}{}{} [0:{}-1];".format(p, r, m.name, m.depth), file=self.file)
            else:
                # remember for SystemVerilog, later
                # # can assume it is a localparam array
                # # build the initial values list
                # vals = []
                # w = m.mem[0]._nrbits
                # for s in m.mem:
                #     vals.append('{}\'d{}'.format(w, _intRepr(s._init)))
                #
                # print('localparam {} {} {} [0:{}-1] = \'{{{}}};'.format(p, r, m.name, m.depth, ', '.join(vals)), file=self.file)
                print('logic {}{} {} [0:{}-1];'.format(p, r, m.name, m.depth), file=self.file)
                val_assignments = '\n'.join(
                            ['    {}[%d] <= {};' %
                             (m.name, n, _intRepr(each._init))
                             for n, each in enumerate(m.mem)])
                initial_assignments = (
                    'initial begin\n' + val_assignments + '\nend')

            if initial_assignments is not None:
                print(initial_assignments, file=self.file)

        print(file=self.file)
        for s in constwires:
            if s._type in (bool, intbv):
                c = int(s.val)
            else:
                raise ToVerilogError("Unexpected type for constant signal", s._name)
            c_len = s._nrbits
            c_str = "{}".format(c)
            print("assign {} = {}'d{};".format(s._name, c_len, c_str), file=self.file)
        # print(file=self.file)

        # shadow signal assignments
        for s in siglist:
            if hasattr(s, 'toVerilog') and s._driven:
                print(s.toVerilog(), file=self.file)
        print(file=self.file)

    def writeModuleFooter(self):
        print("\nendmodule", file=self.file)

    def writeTestBench(self, intf):
        print(f'{self.testbench}: testbench tb_{self.filename} to:  {self.directory} ')
        if self.testbench:
            tbpath = os.path.join(self.directory, "tb_" + self.filename)
            tbfile = open(tbpath, 'w')
            _writeTestBench(tbfile, intf, self.trace)
            tbfile.close()

    def emitline(self):
        pass

    def close(self):
        self.file.close()

    def _cleanup(self):
        # clean up attributes
        self.standard = '2005'
        self.prefer_blocking_assignments = True
        self.radix = ''
        self.header = ""
        self.no_myhdl_header = False
        self.testbench = True
        self.trace = False


class _ConvertVisitor(ast.NodeVisitor, _ConversionMixin):

    def __init__(self, tree, buf, writer):
        self.tree = tree
        self.buf = buf
        self.returnLabel = tree.name
        self.ind = '    '  # start of indented
        self.isSigAss = False
        self.okSigAss = True
        self.labelStack = []
        self.context = _context.UNKNOWN
        self.writer = writer

    def raiseError(self, node, kind, msg=""):
        lineno = self.getLineNo(node)
        info = "in file {}, line {}:\n    ".format(self.tree.sourcefile, self.tree.lineoffset + lineno)
        raise ConversionError(kind, msg, info)

    def write(self, arg):
        self.buf.write("{}".format(arg))

    def writeline(self, nr=1):
        for __ in range(nr):
            self.buf.write("\n{}".format(self.ind))

    def writeDoc(self, node):
        assert hasattr(node, 'doc')
        doc = _makeDoc(node.doc, '// ', self.ind)
        self.write(doc)
        self.writeline()

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
            self.write("{}{}".format(direction, name))
        elif isinstance(obj, int):
            if direction == "input ":
                self.write("input {};".format(name))
                self.writeline()
            self.write("integer {}".format(name))
        elif isinstance(obj, _Ram):
            self.write("logic [{}-1:0] {} [0:{}-1]".format(obj.elObj._nrbits, name, obj.depth))
        elif hasattr(obj, '_nrbits'):
            s = ""
            if isinstance(obj, (intbv, _Signal)):
                if obj._min is not None and obj._min < 0:
                    s = "signed "
            self.write("{}{}[{}-1:0] {}".format(direction, s, obj._nrbits, name))
        else:
            raise AssertionError("var {} has unexpected type {}".format(name, type(obj)))
        # initialize regs
        # if direction == 'reg ' and not isinstance(obj, _Ram):
        # disable for cver
        if False:
            if isinstance(obj, EnumItemType):
                inival = obj._toVerilog()
            else:
                inival = int(obj)
            self.write(" = {};".format(inival))
        else:
            self.write(";")

    def writeDeclarations(self):
        for name, obj in self.tree.vardict.items():
            self.writeline()
            self.writeDeclaration(obj, name, "logic")

    def writeAlwaysHeader(self):
        assert self.tree.senslist
        senslist = self.tree.senslist
        self.write("always ")
        self.writeSensitivityList(senslist)
        self.write(" begin: {}".format(self.tree.name))
        self.indent()

    def writeSensitivityList(self, senslist):
        ic(self.__class__.__name__, senslist)
        sep = ', '
        if self.writer.standard == '1995':
            sep = ' or '
        self.write("@(")
        for e in senslist[:-1]:
            self.write(e._toVerilog())
            self.write(sep)
        self.write(senslist[-1]._toVerilog())
        self.write(")")

    def visit_BinOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
            self.visit(node.left)
            self.write(" {} ".format(opmap[type(node.op)]))
            self.visit(node.right)
            self.write(")")
            self.context = None

    def checkOpWithNegIntbv(self, node, op):
        if op in ("+", "-", "*", "~", "&&", "||", "!"):
            return
        if isinstance(node, ast.Name):
            o = node.obj
            if isinstance(o, (_Signal, intbv)) and o.min is not None and o.min < 0:
                self.raiseError(node, _error.NotSupported,
                                "negative intbv with operator {}".format(op))

    def visit_BoolOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("(")
        self.visit(node.values[0])
        for n in node.values[1:]:
            self.write(" {} ".format(opmap[type(node.op)]))
            self.visit(n)
        self.write(")")

    def visit_UnaryOp(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("({}".format(opmap[type(node.op)]))
        self.visit(node.operand)
        self.write(")")

    def visit_Attribute(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
                self.write("{}".format(node.obj))
        if isinstance(obj, EnumType):
            assert hasattr(obj, node.attr)
            e = getattr(obj, node.attr)
            self.write(e._toVerilog())

    def visit_Assert(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
                    self.write("{}: ".format(i))
                self.visit(node.targets[0])
                if self.isSigAss:
                    self.write(' <= ')
                    self.isSigAss = False
                else:
                    self.write(' = ')
                s = self.IntRepr(n)
                self.write("{};".format(s))
            self.dedent()
            self.writeline()
            self.write("endcase")

        elif isinstance(node.value, ast.ListComp):
            # skip list comprehension assigns for now
            pass

        else:
            # default behavior
            # there should only be a single target
            self.visit(node.targets[0])
            if isinstance(node.targets[0], ast.Attribute) and isinstance(node.value, ast.Constant):
                node.value.dst = node.targets[0].obj
            if self.isSigAss:
                self.write(' <= ')
                self.isSigAss = False
            else:
                self.write(' = ')
            self.visit(node.value)
            self.write(';')
            self.writer.emitline()

    def visit_AugAssign(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        # XXX apparently no signed context required for augmented assigns
        self.visit(node.target)
        self.write(" = ")
        self.visit(node.target)
        self.write(" {} ".format(opmap[type(node.op)]))
        self.visit(node.value)
        self.write(";")
        self.writer.emitline()

    def visit_Break(self, node,):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("disable {};".format(self.labelStack[-2]))
        self.writer.emitline()

    def visit_Call(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
            v = Visitor(node.tree, self.funcBuf, self.writer)
            v.visit(node.tree)

    def visit_Compare(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.context = None
        if node.signed:
            self.context = _context.SIGNED
        self.write("(")
        self.visit(node.left)
        self.write(" {} ".format(opmap[type(node.ops[0])]))
        self.visit(node.comparators[0])
        self.write(")")
        self.context = None

    def visit_Constant(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        if node.value is None:
            # NameConstant
            self.write(nameconstant_map[node.obj])
        elif isinstance(node.value, bool):
            self.write(nameconstant_map[node.obj])
        elif isinstance(node.value, int):
            # Num
            if self.context == _context.PRINT:
                self.write('"{}"' % node.value)
            else:
                if hasattr(node, 'dst') and isinstance(node.dst._val, bool):
                    self.write(nameconstant_map[bool(node.obj)])
                else:
                    self.write(self.IntRepr(node.value))
        elif isinstance(node.value, str):
            # Str
            s = node.value
            if self.context == _context.PRINT:
                self.write('"{}"' % s)
            elif len(s) == s.count('0') + s.count('1'):
                self.write("{}'b{}".format(len(s), s))
            else:
                self.write(s)

    def visit_Continue(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("disable {};".format(self.labelStack[-1]))

    def visit_Expr(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.visit(node.test)
        self.write(' ? ')
        self.visit(node.body)
        self.write(' : ')
        self.visit(node.orelse)

    def visit_For(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
            self.write("begin: {}".format(node.breakLabel))
            self.writeline()
        self.write("for ({}=".format(var))
        if start is None:
            self.write("0")
        else:
            self.visit(start)
        self.write("{}; {}{}".format(oneoff, var, cmp))
        if stop is None:
            self.write("0")
        else:
            self.visit(stop)
        self.write("; {}={}{}".format(var, var, op))
        if step is None:
            self.write("1")
        else:
            v = self.getVal(step)
            self.require(node, v >= 0, "step should be >= 0")
            self.visit(step)
        self.write(") begin")
        if node.loopLabel.isActive:
            self.write(": {}".format(node.loopLabel))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        if node.ignore:
            return
        if node.isCase:
            self.mapToCase(node)
        else:
            self.mapToIf(node)

    def visit_Match(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        item = node.value
        obj = self.getObj(item)

        if isinstance(obj, EnumItemType):
            itemRepr = obj._toVerilog()
        else:
            itemRepr = self.IntRepr(item.value, radix='hex')

        self.write(itemRepr)

    def visit_MatchSingleton(self, node):
        raise AssertionError("Unsupported Match type {} ".format(type(node)))

    def visit_MatchSequence(self, node):
        raise AssertionError("Unsupported Match type {} ".format(type(node)))

    def visit_MatchStar(self, node):
        raise AssertionError("Unsupported Match type {} ".format(type(node)))

    def visit_MatchMapping(self, node):
        raise AssertionError("Unsupported Match type {} ".format(type(node)))

    def visit_MatchClass(self, node):
        for pattern in node.patterns:
            self.visit(pattern)

    def visit_MatchAs(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        if node.name is None and  node.pattern is None:
            self.write("default")
        else:
            raise AssertionError("Unknown name {} or pattern {}".format(node.name, node.pattern))

    def visit_MatchOr(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        self.visit(var)
        self.write(")")
        self.writer.emitline()
        self.indent()
        for test, suite in node.tests:
            self.writeline()
            item = test.case[1]
            if isinstance(item, EnumItemType):
                self.write(item._toVerilog())
            else:
                self.write(self.IntRepr(item, radix='hex'))
            self.write(": begin")
            self.indent()
            self.visit_stmt(suite)
            self.dedent()
            self.writeline()
            self.write("end")
            self.writer.emitline()

        if node.else_:
            self.writeline()
            self.write("default: begin")
            self.indent()
            self.visit_stmt(node.else_)
            self.dedent()
            self.writeline()
            self.write("end")
            self.writer.emitline()

        self.dedent()
        self.writeline()
        self.write("endcase")
        self.writer.emitline()

    def mapToIf(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        first = True
        for test, suite in node.tests:
            if first:
                ifstring = "if ("
                first = False
            else:
                ifstring = "else if ("
                self.writeline()
            self.write(ifstring)
            self.visit(test)
            self.write(") begin")
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]

            self.indent()
            self.visit_stmt(suite)
            self.dedent()
            self.writeline()
            self.write("end")
            self.writer.emitline()

        if node.else_:
            self.writeline()
            self.write("else begin")
            self.writer.emitline()
            # ic(self.writer.ir)
            # del self.writer.ir[:]
            self.indent()
            self.visit_stmt(node.else_)
            self.dedent()
            self.writeline()
            self.write("end")
            self.writer.emitline()

        # final closing end
        self.writer.emitline()

    def visitKeyword(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.visit(node.expr)

    def visit_Module(self, node, *args):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write(node.id)

    def getName(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        n = node.id
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
                s = "1'b{}".format(int(obj))
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
                self.raiseError(node, _error.UnsupportedType, "{}, {} {}".format(n, type(obj), obj))
        else:
            raise AssertionError("name ref: {}".format(n))

        if addSignBit:
            self.write("$signed({1'b0, ")

        if s.startswith('--'):
            self.write(s.replace('--', '//'))
        else:
            self.write(s)
        if addSignBit:
            self.write("})")

    def visit_Pass(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("// pass")

    def visit_Print(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        argnr = 0
        for s in node.format:
            if isinstance(s, str):
                self.write(f'$write("{s}");')
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
                        self.write(f"'b{item._val}: ")
                        self.write(f'$write("{n}");')
                    self.dedent()
                    self.writeline()
                    self.write("endcase")
                else:
                    self.write(f'$write("{fs}", ')
                    self.visit(a)
                    self.write(');')
                self.context = _context.UNKNOWN
            self.writeline()
        self.write('$write("\\n");')

    def visit_Raise(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        self.write("$finish;")

    def visit_Return(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        self.write("disable {};".format(self.returnLabel))

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            self.accessSlice(node)
        else:
            self.accessIndex(node)

    def accessSlice(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        if isinstance(node.value, ast.Call) and \
           node.value.func.obj in (intbv, modbv) and \
           _isConstant(node.value.args[0], self.tree.symdict):
            c = self.getVal(node)
            self.write("{}'h".format(c._nrbits))
            self.write("{:x}".format(c._val))
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
        if lower is None:
            self.write("{}".format(node.obj._nrbits))
        else:
            self.visit(lower)

        self.write("-1:")
        if upper is None:
            self.write("0")
        else:
            self.visit(upper)

        self.write("]")
        if addSignBit:
            self.write("})")

    def accessIndex(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        addSignBit = isinstance(node.ctx, ast.Load) and \
            (not node.signed) and \
            (self.context == _context.SIGNED)
        if addSignBit:
            self.write("$signed({1'b0, ")
        self.context = None
        self.visit(node.value)
        self.write("[")
        # assert len(node.subs) == 1
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: no ast.Index wrapper
            self.visit(node.slice)
        else:
            self.visit(node.slice.value)
        self.write("]")
        if addSignBit:
            self.write("})")

    def visit_stmt(self, body):
        # 'body' is a list of statements
        ic(self.__class__.__name__, body, (vars(self)))
        for stmt in body:
            ic(self.__class__.__name__, astdump(stmt, show_offsets=False), (vars(stmt)))
            self.writeline()
            self.visit(stmt)
            # ugly hack to detect an orphan "task" call
            if isinstance(stmt, ast.Call) and hasattr(stmt, 'tree'):
                self.write(';')

    def visit_Tuple(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        assert self.context != None
        sep = ", "
        tpl = node.elts
        self.visit(tpl[0])
        for elt in tpl[1:]:
            self.write(sep)
            self.visit(elt)

    def visit_While(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        self.labelStack.append(node.breakLabel)
        self.labelStack.append(node.loopLabel)
        if node.breakLabel.isActive:
            self.write("begin: {}".format(node.breakLabel))
            self.writeline()
        self.write("while (")
        self.visit(node.test)
        self.write(") begin")
        if node.loopLabel.isActive:
            self.write(": {}".format(node.loopLabel))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.writeDoc(node)
        w = node.body[-1]
        y = w.body[0]
        if isinstance(y, ast.Expr):
            y = y.value
        assert isinstance(y, ast.Yield)
        self.writeAlwaysHeader()
        self.writeDeclarations()
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.writeDoc(node)
        self.write("initial begin: {}".format(self.tree.name))
        self.indent()
        # self.writeDeclarations(self.tree)
        self.writeDeclarations()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertAlwaysCombVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        if self.writer.prefer_blocking_assignments:
            self.okSigAss = False
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self)))
        self.writeDoc(node)
        self.writeAlwaysHeader()
        self.writeDeclarations()
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        if isinstance(node.ctx, ast.Store):
            # try intercepting '-- OpenPort' signals
            if isinstance(node.value, ast.Name):
                obj = self.tree.symdict[node.value.id]
                if obj._name.startswith('-- OpenPort'):
                    self.write('// ')

            self.write("assign ")
            self.visit(node.value)
        else:
            self.getAttr(node)

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.writeDoc(node)
        self.visit_stmt(node.body)
        self.writeline(2)


class _ConvertAlwaysDecoVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.writeDoc(node)
        self.writeAlwaysHeader()
        self.writeDeclarations()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline(2)


class _ConvertAlwaysSeqVisitor(_ConvertVisitor):

    def __init__(self, tree, blockBuf, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, blockBuf, writer)
        self.funcBuf = funcBuf

    def visit_FunctionDef(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)), (vars(self.tree)))
        self.writeDoc(node)
        self.writeAlwaysHeader()
        self.writeDeclarations()
        reset = self.tree.reset
        sigregs = self.tree.sigregs
        varregs = self.tree.varregs
        if reset is not None:
            self.writeline()
            self.write("if ({} == {}) begin".format(reset, int(reset.active)))
            self.indent()
            for s in sigregs:
                self.writeline()
                self.write("{} <= {};".format(s, self._convertInitVal(s, s._init)))
            for v in varregs:
                n, reg, init = v
                self.writeline()
                self.write("{} = {};".format(n, self._convertInitVal(reg, init)))
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

    def _convertInitVal(self, reg, init):
        if isinstance(reg, _Signal):
            tipe = reg._type
        else:
            assert isinstance(reg, intbv)
            tipe = intbv
        if tipe is bool:
            v = '1' if init else '0'
        elif tipe is intbv:
            init = int(init)  # int representation
            v = "{}".format(init) if init is not None else "'bz"
        else:
            assert isinstance(init, EnumItemType), '<> {}'.format(repr(init))
            v = init._toVerilog()
        return v


class _ConvertFunctionVisitor(_ConvertVisitor):

    def __init__(self, tree, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, funcBuf, writer)
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("function ")
        self.writeOutputDeclaration()
        self.indent()
        self.writeInputDeclarations()
        self.writeDeclarations()
        self.dedent()
        self.writeline()
        self.write("begin: {}".format(self.returnLabel))
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline()
        self.write("endfunction")
        self.writeline(2)

    def visit_Return(self, node):
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("{} = ".format(self.tree.name))
        self.visit(node.value)
        self.write(";")
        self.writeline()
        self.write("disable {};".format(self.returnLabel))


class _ConvertTaskVisitor(_ConvertVisitor):

    def __init__(self, tree, funcBuf, writer):
        _ConvertVisitor.__init__(self, tree, funcBuf, writer)
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
        ic(self.__class__.__name__, astdump(node, show_offsets=False), (vars(node)))
        self.write("task {};".format(self.tree.name))
        self.indent()
        self.writeInterfaceDeclarations()
        self.writeDeclarations()
        self.dedent()
        self.writeline()
        self.write("begin: {}".format(self.returnLabel))
        self.indent()
        self.visit_stmt(node.body)
        self.dedent()
        self.writeline()
        self.write("end")
        self.writeline()
        self.write("endtask")
        self.writeline(2)


myhdl_header = """\
// File: $filename
// Generated by MyHDL $version
// Date: $date
"""


def _writeTestBench(f, intf, trace=False):
    print(f"module tb_{intf.name};", file=f)
    print(file=f)
    fr = StringIO()
    to = StringIO()
    pm = StringIO()
    for portname in intf.argnames:
        s = intf.argdict[portname]
        r = _getRangeString(s)
        if s._driven:
            print("logic {}{};".format(r, portname), file=f)
            print("        {},".format(portname), file=to)
        else:
            print("logic {}{};".format(r, portname), file=f)
            print("        {},".format(portname), file=fr)
        print("    {},".format(portname), file=pm)
    print(file=f)
    print("initial begin", file=f)
    if trace:
        print('    $dumpfile("{}.vcd");' % intf.name, file=f)
        print('    $dumpvars(0, dut);', file=f)
    if fr.getvalue():
        print("    $from_myhdl(", file=f)
        print(fr.getvalue()[:-2], file=f)
        print("    );", file=f)
    if to.getvalue():
        print("    $to_myhdl(", file=f)
        print(to.getvalue()[:-2], file=f)
        print("    );", file=f)
    print("end", file=f)
    print(file=f)
    print("{} dut(".format(intf.name), file=f)
    print(pm.getvalue()[:-2], file=f)
    print(");", file=f)
    print(file=f)
    print("endmodule", file=f)


def _getRangeString(s):
    if s._type is bool:
        return ''
    elif s._nrbits is not None:
        nrbits = s._nrbits
        return "[{}:0] ".format(nrbits - 1)
    else:
        raise AssertionError


def _getSignString(s):
    if s._min is not None and s._min < 0:
        return "signed "
    else:
        return ''


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
    r = "{}{}{}".format(size, radix, num)
    if n < 0:  # add brackets and sign on negative numbers
        r = "(-{})".format(r)
    return r


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
if __name__ == '__main__':
    pass

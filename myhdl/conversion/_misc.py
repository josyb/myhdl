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

""" myhdl conversion package.

"""
import inspect
import ast
from datetime import datetime, timezone
import re

from myhdl import ConversionError
from myhdl._enum import EnumItemType
from myhdl._intbv import intbv
from myhdl._Signal import _Signal


class _error(object):
    ArgType = "leaf cell type error"
    ExtraArguments = "Extra positional or named arguments are not supported"
    FirstArgType = "first argument should be a classic function"
    FormatString = "Format string error"
    FreeVarTypeError = "Free variable should be a Signal or an int"
    # IntbvSign = "intbv's that can have negative values are not yet supported"
    IntbvBitWidth = "intbv object should have a bit width"
    ListAsPort = "List of signals as a port is not supported"
    ListElementAssign = "Can't assign to list element; use slice assignment to change its value"
    MissingNext = "Missing '.next' attribute in assignment"
    ModbvRange = "modbv object should have full bit vector range"
    NrBitsMismatch = "Nr of bits mismatch with earlier assignment"
    NotASignal = "Non-local object should be a Signal"
    NotSupported = "Not supported"
    OutputPortRead = "Output port is read internally"
    PortInList = "Port in list is not supported"
    ReturnTypeMismatch = "Return type mismatch"
    ReturnNrBitsMismatch = "Returned nr of bits mismatch"
    ReturnIntbvBitWidth = "Returned intbv instance should have bit width"
    ReturnTypeInfer = "Can't infer return type"
    Requirement = "Requirement violation"
    ShadowingSignal = "Port is not used or shadowed by internal signal"
    ShadowingVar = "Variable has same name as a hierarchical Signal"
    SignalInMultipleLists = "Signal in multiple list is not supported"
    SigMultipleDriven = "Signal has multiple drivers"
    TopLevelName = "Result of toVerilog call should be assigned to a top level name"
    TypeInfer = "Can't infer variable type"
    TypeMismatch = "Type mismatch with earlier assignment"
    UndefinedBitWidth = "Signal has undefined bit width"
    UndrivenSignal = "Signal is not driven"
    UnreadSignal = "Signal is driven but not read"
    UnusedPort = "Port is not used"
    UnboundLocal = "Local variable may be referenced before assignment"
    UnsupportedYield = "Unsupported yield statement"
    UnsupportedListComp = "Unsupported list comprehension form: should be [intbv()[n:] for i in range(m)]"
    UnsupportedType = "Object type is not supported in this context"
    InconsistentType = "Signal elements should have the same base type"
    InconsistentBitWidth = "Signal elements should have the same bit width"
    UnsupportedFormatString = "Unsupported format string"
    UnsupportedAttribute = "Unsupported attribute"
    UnkownConvertor = "Unknown target language"


class _access(object):
    INPUT, OUTPUT, INOUT, UNKNOWN = range(4)


class _kind(object):
    NORMAL, DECLARATION, ALWAYS, INITIAL, ALWAYS_DECO, \
        ALWAYS_COMB, SIMPLE_ALWAYS_COMB, ALWAYS_SEQ, \
        TASK, REG \
 = range(10)


class _context(object):
    BOOLEAN, YIELD, PRINT, SIGNED, UNKNOWN = range(5)


class _ConversionMixin(object):

    #     def getLineNo(self, node):
    #         lineno = node.lineno
    #         if lineno is None:
    #             for n in node.getChildNodes():
    #                 if n.lineno is not None:
    #                     lineno = n.lineno
    #                     break
    #         lineno = lineno or 0
    #         return lineno

    def getLineNo(self, node):
        lineno = 0
        if isinstance(node, (ast.stmt, ast.expr)):
            lineno = node.lineno
        return lineno

    def getObj(self, node):
        if hasattr(node, 'obj'):
            return node.obj
        return None

    def getTarget(self, node):
        if hasattr(node, 'target'):
            return node.target
        return None

    def getKind(self, node):
        if hasattr(node, 'kind'):
            return node.kind
        return None

    def getEdge(self, node):
        if hasattr(node, 'edge'):
            return node.edge
        return None

    def getValue(self, node):
        if hasattr(node, 'value'):
            return node.value
        return None

    def getVal(self, node):
        expr = ast.Expression()
        expr.body = node
        expr.lineno = node.lineno
        expr.col_offset = node.col_offset
        c = compile(expr, '<string>', 'eval')
        val = eval(c, self.tree.symdict, self.tree.vardict)
        # val = eval(_unparse(node), self.tree.symdict, self.tree.vardict)
        return val

    def raiseError(self, node, kind, msg=""):
        lineno = self.getLineNo(node)
        info = "in file %s, line %s:\n    " % \
            (self.tree.sourcefile, self.tree.lineoffset + lineno)
        raise ConversionError(kind, msg, info)

    def require(self, node, test, msg=""):
        assert isinstance(node, ast.AST)
        if not test:
            self.raiseError(node, _error.Requirement, msg)

    def visitChildNodes(self, node, *args):
        for n in node.getChildNodes():
            self.visit(n, *args)

    def visitList(self, nodes):
        for n in nodes:
            self.visit(n)


def _LabelGenerator():
    i = 1
    while 1:
        yield "MYHDL%s" % i
        i += 1


_genLabel = _LabelGenerator()


class _loopInt(int):
    pass


class _Label(object):

    def __init__(self, name):
        self.name = next(_genLabel) + '_' + name
        self.isActive = False

    def __str__(self):
        return str(self.name)


# type inference
class sig_type(object):

    def __init__(self, size=0):
        self.size = size

    def __repr__(self):
        return "{}({})".format(type(self).__name__, self.size)


class sig_string(sig_type):
    pass


class sig_enum(sig_type):

    def __init__(self, tipe):
        self._type = tipe

    def toStr(self, constr=True):
        return self._type.__dict__['_name']


class sig_std_logic(sig_type):

    def __init__(self):
        sig_type.__init__(self)
        self.size = 1

    def toStr(self, constr=True):
        return 'std_logic'


class sig_boolean(sig_type):

    def __init__(self, size=0):
        sig_type.__init__(self)
        self.size = 1

    def toStr(self, constr=True):
        return 'boolean'


class sig_vector(sig_type):

    def __init__(self, size=0):
        sig_type.__init__(self, size)


class sig_unsigned(sig_vector):

    def toStr(self, constr=True):
        if constr:
            return "unsigned({} downto 0)".format(self.size - 1)
        else:
            return "unsigned"


class sig_signed(sig_vector):

    def toStr(self, constr=True):
        if constr:
            return "signed({} downto 0)".format(self.size - 1)
        else:
            return "signed"


class sig_int(sig_type):

    def toStr(self, constr=True):
        return "integer"


class sig_nat(sig_int):

    def toStr(self, constr=True):
        return "natural"


def inferSigObj(obj):
    sig = None
    if (isinstance(obj, _Signal) and obj._type is intbv) or \
       isinstance(obj, intbv):
        if obj.min is None or obj.min < 0:
            sig = sig_signed(size=len(obj))
        else:
            sig = sig_unsigned(size=len(obj))
    elif (isinstance(obj, _Signal) and obj._type is bool) or \
            isinstance(obj, bool):
        sig = sig_std_logic()
    elif (isinstance(obj, _Signal) and isinstance(obj._val, EnumItemType)) or\
            isinstance(obj, EnumItemType):
        if isinstance(obj, _Signal):
            tipe = obj._val._type
        else:
            tipe = obj._type
        sig = sig_enum(tipe)
    elif isinstance(obj, int):
        if obj >= 0:
            sig = sig_nat()
        else:
            sig = sig_int()
        # sig = sig_int()
    return sig


# this can be made more sophisticated to deal with existing suffixes
# also, may require reset facility
class _UniqueSuffixGenerator(object):

    def __init__(self):
        self.i = 0

    def reset(self):
        self.i = 0

    def next(self):
        self.i += 1
        return "_%s" % self.i


_genUniqueSuffix = _UniqueSuffixGenerator()


# check if expression is constant
def _isConstant(tree, symdict):
    v = _namesVisitor()
    v.visit(tree)
    for name in v.names:
        if name not in symdict:
            return False
        if not isinstance(symdict[name], int):
            return False
    return True


class _namesVisitor(ast.NodeVisitor):

    def __init__(self):
        self.names = []

    def visit_Name(self, node):
        self.names.append(node.id)


def _get_argnames(node):
    return [arg.arg for arg in node.args.args]


def _makeDoc(doc, comment, indent=''):
    if doc is None:
        return ''
    pre = '\n' + indent + comment
    doc = inspect.cleandoc(doc)
    doc = doc.replace('\n', pre)
    return indent + comment + doc


def getutcdatetime():
    # get the current utc time
    t = datetime.now(timezone.utc)
    # convert to unix, this will keep the utc timezone
    unix = t.timestamp()
    # convert back to datetime, specifying that the timestamp is in UTC
    t2 = '{}'.format(datetime.fromtimestamp(unix, tz=timezone.utc))
    # leave out milliseconds etc.
    return '{} UTC'.format(t2[:19])


def natural_key(string_):
    """
        a helper routine to 'improve' the sort
        See http://www.codinghorror.com/blog/archives/001018.html
    """
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]


def sortalign(sl, sort=False, port=False, sep=':'):
    '''
        aligning and sorting strings
        oroignally tailored for VHDL
        so will need work for Verilog and SystemVerilog?
    '''
    # align the colons
    maxpos = 0
    for l in sl:
        if sep in l:
            t = l.find(sep)
            maxpos = t if t > maxpos else maxpos

    if maxpos:
        for i, l in enumerate(sl):
            if sep in l:
                p = l.find(sep)
                b, c, e = l.partition(sep)
                sl[i] = b + ' ' * (maxpos - p) + c + e

    # align after 'in', 'out' or 'inout'
    if port:
        portdirections = (': in', ': out', ': inout')
        maxpos = 0
        for l in sl:
            for tst in portdirections:
                if tst in l:
                    t = l.find(tst) + len(tst)
                    maxpos = t if t > maxpos else maxpos
                    continue
        if maxpos:
            for i, l in enumerate(sl):
                for tst in portdirections:
                    if tst in l:
                        p = l.find(tst)
                        b, c, e = l.partition(tst)
                        sl[i] = b + c + ' ' * (maxpos - p - len(tst)) + e

    # align then :=' if any
    maxpos = 0
    for l in sl:
        if ':=' in l:
            t = l.find(':=')
            maxpos = t if t > maxpos else maxpos
    if maxpos:
        for i, l in enumerate(sl):
            if ':=' in l:
                p = l.find(':=')
                b, c, e = l.partition(':=')
                sl[i] = b + ' ' * (maxpos - p) + c + e

    if sort:
        # sort the signals
        return sorted(sl, key=natural_key)
    else:
        return sl

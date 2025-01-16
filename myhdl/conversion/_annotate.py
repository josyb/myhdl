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

'''
Created on 2 jan. 2025

@author: josy

        split out from _convertor.py to keep that module a bit smaller

'''
import sys
import math
import ast

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True,
                   prefix='')
from astpretty import pformat as astdump
import pprint
pp = pprint.PrettyPrinter(indent=4, width=120)

# from myhdl import  ConversionError
# from myhdl._instance import _Instantiator
# from myhdl._block import _Block
# from myhdl._concat import concat
# from myhdl._enum import EnumType, EnumItemType
from myhdl._extractHierarchy import  _UserCode
# from myhdl._getHierarchy import _getHierarchy
from myhdl._intbv import intbv
# from myhdl._modbv import modbv
# from myhdl._Signal import Signal, _WaiterList, posedge, negedge, Constant
# from myhdl._simulator import now
# from myhdl.conversion._analyze import (_analyzeSigs, _analyzeGens, _Ram, _Rom)
from myhdl.conversion._misc import (_error, _kind, _ConversionMixin, _genUniqueSuffix,
                                    sig_boolean, sig_enum, sig_int, sig_nat, sig_signed,
                                    sig_std_logic, sig_string, sig_type, sig_unsigned, sig_vector, inferSigObj, _loopInt)
from myhdl.conversion._hierarchical import _HierarchicalInstance


class _AnnotateTypesVisitor(ast.NodeVisitor, _ConversionMixin):

    def __init__(self, tree, hdl):
        self.tree = tree
        self.hdl = hdl

    def visit_FunctionDef(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # don't visit arguments and decorators
        for stmt in node.body:
            # ic(self.__class__.__name__, astdump(stmt, show_offsets=False))
            self.visit(stmt)
        # ic.dedent()

    def visit_Assert(self, node):
        # ic.indent()
        # ic.enable()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.visit(node.test)
        # node.test.sig = sig_boolean()
        # ic.dedent()
        # ic.disable()

    # def visit_Assign(self, node):
    #     ''' this is only for completeness '''
    #     # ic.indent()
    #     # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
    #     self.generic_visit(node)
    #     # ic.dedent()

    # def visit_Attribute(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
    #     if isinstance(node.ctx, ast.Store):
    #         # self.setAttr(node)
    #         # self.visit(node.value)
    #         pass
    #     else:
    #         # self.getAttr(node)
    #         node.signed = False
    #     self.visit(node.value)
    #     node.sig = inferSigObj(node.obj)
    #     node.sigOri = copy(node.sig)

    # def setAttr(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
    #     self.visit(node.value)
    #
    # def getAttr(self, node):
    #     ic(self.__class__.__name__, astdump(node, show_offsets=False))
    #     node.signed = False
    #     self.visit(node.value)

    def visit_Attribute(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if isinstance(node.ctx, ast.Store):
            self.setAttr(node)
        else:
            self.getAttr(node)
        # # VHDL
        # node.obj = self.getObj(node.value)
        # node.sig = inferSigObj(node.obj)
        # node.sigOri = copy(node.sig)
        # ic(self.__class__.__name__, pp.pformat(vars(node)))
        # ic.dedent()

    def setAttr(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # assert node.attr == 'next'
        # self.SigAss = True
        # self.dst = None
        # if isinstance(node.value, ast.Name):
        #     sig = self.tree.symdict[node.value.id]
        #     self.SigAss = sig._name
        #     self.dst = sig
        #     # ic('self.SigAss:', self.SigAss, repr(self.dst))

        self.visit(node.value)

    def getAttr(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # if self.hdl == 'VHDL':
        #     if isinstance(node.value, ast.Subscript):
        #         self.setAttr(node)
        #         return
        #
        #     assert isinstance(node.value, ast.Name), node.value
        #     n = node.value.id
        #     if n in self.tree.symdict:
        #         obj = self.tree.symdict[n]
        #     elif n in self.tree.vardict:
        #         obj = self.tree.vardict[n]
        #     else:
        #         raise AssertionError("object not found")
        #     if isinstance(obj, _Signal):
        #         if node.attr == 'next':
        #             sig = self.tree.symdict[node.value.id]
        #             self.SigAss = obj._name
        #             self.visit(node.value)
        #         elif node.attr == 'posedge':
        #             self.write("rising_edge(")
        #             self.visit(node.value)
        #             self.write(")")
        #         elif node.attr == 'negedge':
        #             self.write("falling_edge(")
        #             self.visit(node.value)
        #             self.write(")")
        #         elif node.attr == 'val':
        #             pre, suf = self.inferCast(node.vhd, node.vhdOri)
        #             self.write(pre)
        #             self.visit(node.value)
        #             self.write(suf)
        #     if isinstance(obj, (_Signal, intbv)):
        #         if node.attr in ('min', 'max'):
        #             pre, suf = self.inferCast(node.vhd, node.vhdOri)
        #             self.write(pre)
        #             self.write("%s" % node.obj)
        #             self.write(suf)
        #     if isinstance(obj, EnumType):
        #         assert hasattr(obj, node.attr)
        #         e = getattr(obj, node.attr)
        #         self.write(e._toVHDL())
        # else:
        node.signed = False
        self.visit(node.value)

    def visit_AugAssign(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.visit(node.target)
        self.visit(node.value)
        # if isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor)):
        #     node.value.sig = copy(node.target.sig)
        #     node.sigOri = copy(node.target.sig)
        # elif isinstance(node.op, (ast.RShift, ast.LShift)):
        #     node.value.sig = sig_int()
        #     node.sigOri = copy(node.target.sig)
        # else:
        #     node.left, node.right = node.target, node.value
        #     self.inferBinOpType(node)
        # node.sig = copy(node.target.sig)
        # ic.dedent()

    def visit_BinOp(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.visit(node.left)
        self.visit(node.right)
        node.signed = node.left.signed or node.right.signed
        # # special treatement of subtraction unless in a top-level rhs
        # if isinstance(node.op, ast.Sub) and not hasattr(node, 'isRhs'):
        #     node.signed = True
        # if isinstance(node.op, (ast.LShift, ast.RShift)):
        #     self.inferShiftType(node)
        # elif isinstance(node.op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
        #     self.inferBitOpType(node)
        # elif isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Str):  # format string
        #     pass
        # else:
        #     self.inferBinOpType(node)
        # ic.dedent()

    # def inferBinOpType(self, node):
    #     left, op, right = node.left, node.op, node.right
    #     if isinstance(left.sig, (sig_boolean, sig_std_logic)):
    #         left.sig = sig_unsigned(1)
    #     if isinstance(right.sig, (sig_boolean, sig_std_logic)):
    #         right.sig = sig_unsigned(1)
    #     if isinstance(right.sig, sig_unsigned):
    #         if maybeNegative(left.sig) or \
    #            (isinstance(op, ast.Sub) and not hasattr(node, 'isRhs')):
    #             right.sig = sig_signed(right.sig.size + 1)
    #     if isinstance(left.sig, sig_unsigned):
    #         if maybeNegative(right.sig) or \
    #            (isinstance(op, ast.Sub) and not hasattr(node, 'isRhs')):
    #             left.sig = sig_signed(left.sig.size + 1)
    #     l, r = left.sig, right.sig
    #     ls, rs = l.size, r.size
    #     if isinstance(r, sig_vector) and isinstance(l, sig_vector):
    #         if isinstance(op, (ast.Add, ast.Sub)):
    #             s = max(ls, rs)
    #         elif isinstance(op, ast.Mod):
    #             s = rs
    #         elif isinstance(op, ast.FloorDiv):
    #             s = ls
    #         elif isinstance(op, ast.Mult):
    #             s = ls + rs
    #         else:
    #             raise AssertionError("unexpected op %s" % op)
    #     elif isinstance(l, sig_vector) and isinstance(r, sig_int):
    #         if isinstance(op, (ast.Add, ast.Sub, ast.Mod, ast.FloorDiv)):
    #             s = ls
    #         elif isinstance(op, ast.Mult):
    #             s = 2 * ls
    #         else:
    #             raise AssertionError("unexpected op %s" % op)
    #     elif isinstance(l, sig_int) and isinstance(r, sig_vector):
    #         if isinstance(op, (ast.Add, ast.Sub, ast.Mod, ast.FloorDiv)):
    #             s = rs
    #         elif isinstance(op, ast.Mult):
    #             s = 2 * rs
    #         else:
    #             raise AssertionError("unexpected op %s" % op)
    #     if isinstance(l, sig_int) and isinstance(r, sig_int):
    #         node.sig = sig_int()
    #     elif isinstance(l, (sig_signed, sig_int)) and isinstance(r, (sig_signed, sig_int)):
    #         node.sig = sig_signed(s)
    #     elif isinstance(l, (sig_unsigned, sig_int)) and isinstance(r, (sig_unsigned, sig_int)):
    #         node.sig = sig_unsigned(s)
    #     else:
    #         node.sig = sig_int()
    #     node.sigOri = copy(node.sig)

    def visit_BoolOp(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False))
        # if self.hdl == 'VHDL':
        #     # VHDL
        #     self.generic_visit(node)
        #     for n in node.values:
        #         n.sig = sig_boolean()
        #     node.sig = sig_boolean()
        #     node.sigOri = copy(node.sig)
        # else:
        for n in node.values:
            self.visit(n)
        node.signed = False
        # ic.dedent()

    def visit_Call(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        f = self.getObj(node.func)
        # node.sig = inferSigObj(node.obj)
        node.signed = False
        self.generic_visit(node)

        if f == intbv.signed: # note equality comparison
            node.signed = True
            # this comes from a getattr
            # node.sig = sig_int()
        #     node.sig = sig_signed(f.value.sig.size)
        # elif f is concat:
        #     ic(self.__class__.__name__, node.args)
        #     s = 0
        #     for a in node.args:
        #         a.sig = inferSigObj(a)
        #         if isinstance(a, ast.Str):
        #             a.sig = sig_unsigned(a.sig.size)
        #         elif isinstance(a.sig, sig_signed):
        #             a.sig = sig_unsigned(a.sig.size)
        #         s += a.sig.size
        #     node.sig = sig_unsigned(s)
        # elif f is bool:
        #     node.sig = sig_boolean()
        # elif f in (int, ord):
        #     node.sig = sig_int()
        #     node.args[0].sig = sig_int()
        # elif f in (intbv, modbv):
        #     node.sig = sig_int()
        # elif f is len:
        #     node.sig = sig_int()
        # elif f is now:
        #     node.sig = sig_nat()
        elif hasattr(node, 'tree'):
            v = _AnnotateTypesVisitor(node.tree, self.hdl)
            v.visit(node.tree)
            node.signed = _maybeNegative(node.tree.returnObj)
            # node.sig = node.tree.sig = inferSigObj(node.tree.returnObj)
        # node.sigOri = copy(node.sig)
        # ic.dedent()
        # ic(self.__class__.__name__, pp.pformat(vars(node)))

    def visit_Compare(self, node):
        # ic.enable()
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = False
        # node.sig = sig_boolean()
        # for n in ast.iter_child_nodes(node):
        for n in [node.left] + node.comparators:
            self.visit(n)
            if n.signed:
                node.signed = True
        # self.generic_visit(node)
        # left, __, right = node.left, node.ops[0], node.comparators[0]
        # if isinstance(left.sig, sig_std_logic) or isinstance(right.sig, sig_std_logic):
        #     left.sig = right.sig = sig_std_logic()
        # elif isinstance(left.sig, sig_unsigned) and maybeNegative(right.sig):
        #     left.sig = sig_signed(left.sig.size + 1)
        # elif maybeNegative(left.sig) and isinstance(right.sig, sig_unsigned):
        #     right.sig = sig_signed(right.sig.size + 1)
        # node.sigOri = copy(node.sig)
        # ic.dedent()
        # ic.disable()

    def visit_Constant(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = False

        # if node.value is None:
        #     # NameConstant
        #     node.sig = inferSigObj(node.value)
        # elif isinstance(node.value, bool):
        #     # NameConstant
        #     node.sig = inferSigObj(node.value)
        # elif isinstance(node.value, int):
        #     # Num
        #     if node.value < 0:
        #         node.sig = sig_int()
        #     else:
        #         node.sig = sig_nat()
        # elif isinstance(node.value, str):
        #     # Str
        #     node.sig = sig_string()
        # node.sigOri = copy(node.sig)
        # ic.dedent()

    def visit_For(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        var = node.target.id
        # make it possible to detect loop variable
        self.tree.vardict[var] = _loopInt(-1)
        self.generic_visit(node)
        # ic.dedent()

    def visit_If(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        if node.ignore:
            # ic.dedent()
            return
        self.generic_visit(node)
        # for test, __ in node.tests:
        #     test.sig = sig_boolean()
        # ic.dedent()

    def visit_IfExp(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.generic_visit(node)
        # node.test.sig = sig_boolean()
        # ic.dedent()

    def visit_ListComp(self, node):
        pass  # do nothing

    def visit_Name(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        # if node.id in self.tree.vardict:
        #     node.obj = self.tree.vardict[node.id]
        if isinstance(node.ctx, ast.Store):
            self.setName(node)
        else:
            self.getName(node)
        # node.sig = inferSigObj(node.obj)
        # node.sigOri = copy(node.sig)
        # ic.dedent()

    def setName(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        pass

    def getName(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = _maybeNegative(node.obj)

    def visit_Subscript(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.slice.toint = True
        if isinstance(node.slice, ast.Slice):
            self.accessSlice(node)
        else:
            self.accessIndex(node)
        # ic(self.__class__.__name__, pp.pformat(vars(node)))
        # ic.dedent()

    def accessSlice(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = False
        self.generic_visit(node)
        # lower = node.value.sig.size
        # t = type(node.value.sig)
        # # node.expr.sig = sig_unsigned(node.expr.sig.size)
        # if node.slice.lower:
        #     node.slice.lower.sig = sig_int()
        #     lower = self.getVal(node.slice.lower)
        # upper = 0
        # if node.slice.upper:
        #     node.slice.upper.sig = sig_int()
        #     upper = self.getVal(node.slice.upper)
        # if isinstance(node.ctx, ast.Store):
        #     node.sig = t(lower - upper)
        # else:
        #     node.sig = sig_unsigned(lower - upper)
        # node.sigOri = copy(node.sig)

    def accessIndex(self, node):
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = _maybeNegative(node.obj)
        self.generic_visit(node)
        # node.sig = sig_std_logic()  # XXX default
        # if sys.version_info >= (3, 9, 0):  # Python 3.9+: no ast.Index wrapper
        #     node.slice.sig = sig_int()
        # else:
        #     node.slice.value.sig = sig_int()
        # obj = node.value.obj
        # if isinstance(obj, list):
        #     assert len(obj)
        #     node.sig = inferSigObj(obj[0])
        # elif isinstance(obj, _Ram):
        #     node.sig = inferSigObj(obj.elObj)
        # elif isinstance(obj, _Rom):
        #     node.sig = sig_int()
        # elif isinstance(obj, intbv):
        #     node.sig = sig_std_logic()
        # node.sigOri = copy(node.sig)

    def visit_Tuple(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        node.signed = False
        self.generic_visit(node)
        # ic.dedent()

    def visit_UnaryOp(self, node):
        # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False))
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
        # node.sig = copy(node.operand.sig)
        # if isinstance(node.op, ast.Not):
        #     # postpone this optimization until initial values are written
        #     #            if isinstance(node.operand.sig, sig_std_logic):
        #     #                node.sig = sig_std_logic()
        #     #            else:
        #     #                node.sig = node.operand.sig = sig_boolean()
        #     node.sig = node.operand.sig = sig_boolean()
        # elif isinstance(node.op, ast.USub):
        #     if isinstance(node.sig, sig_unsigned):
        #         node.sig = sig_signed(node.sig.size + 1)
        #     elif isinstance(node.sig, sig_nat):
        #         node.sig = sig_int()
        # node.sigOri = copy(node.sig)
        # ic.dedent()

    def visit_While(self, node):
        # # ic.indent()
        # ic(self.__class__.__name__, astdump(node, show_offsets=False), pp.pformat(vars(node)))
        self.generic_visit(node)
        # ic.dedent()


def _annotateTypes(hdl, genlist):
    for tree in genlist:
        if isinstance(tree, (_UserCode, _HierarchicalInstance)):
            continue
        v = _AnnotateTypesVisitor(tree, hdl)
        v.visit(tree)


def _maybeNegative(obj):
    if hasattr(obj, '_min') and (obj._min is not None) and (obj._min < 0):
        return True
    if isinstance(obj, int) and obj < 0:
        return True
    return False

# def maybeNegative(sig):
#     if isinstance(sig, sig_signed):
#         return True
#     if isinstance(sig, sig_int) and not isinstance(sig, sig_nat):
#         return True
#     return False


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
    if n < 0: # add brackets and sign on negative numbers
        r = "(-{})".format(r)
    return r


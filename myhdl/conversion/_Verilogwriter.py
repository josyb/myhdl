'''
Created on 29 okt. 2023

@author: josy
'''

import os
import math
import textwrap

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True)

import inspect
from datetime import datetime
import ast
import string
from io import StringIO

import warnings

from myhdl import __version__ as myhdlversion
from myhdl import ToVerilogError, ToVerilogWarning
from myhdl._extractHierarchy import (_UserVerilogCode, _userCodeMap)
from myhdl._Signal import Constant, _Signal
from myhdl._intbv import intbv
from myhdl._enum import EnumItemType
from myhdl._ShadowSignal import _TristateSignal, _TristateDriver
from myhdl.conversion._misc import _error, _makeDoc
from myhdl.conversion._analyze import (_analyzeSigs, _analyzeGens, _Ram, _Rom)


class VerilogWriter(object):
    __slots__ = ("timescale",
                 "standard",
                 "prefer_blocking_assignments",
                 "radix",
                 "header",
                 "no_myhdl_header",
                 "no_testbench",
                 "portmap",
                 "trace",
                 "initial_values",
                 "usercode",
                 "file",
                 "hdl",
                 "comment",
                 "path",
                 "filename",
                 "ind",
                 "ir"
                 )

    def __init__(self, **kwargs):
        self.hdl = 'verilog'
        self.comment = '// '
        self.timescale = "1ns/10ps"
        self.standard = '2005'
        self.prefer_blocking_assignments = True
        self.radix = ''
        self.header = ''
        self.no_myhdl_header = False
        self.no_testbench = True
        self.trace = False
        self.initial_values = False
        self.usercode = _UserVerilogCode
        self.ind = ''
        self.ir = []
        for key, value in kwargs.items():
            ic("{0} = {1}".format(key, value))

    def openfile(self, name, directory):
        self.filename = name + ".v"
        self.path = os.path.join(directory, self.filename)
        setattr(self, 'file', open(self.path, 'w'))

    def writeFileHeader(self):
        vvars = dict(filename=self.filename,
                    version=myhdlversion,
                    date=datetime.today().ctime()
                    )
        if not self.no_myhdl_header:
            print(string.Template(myhdl_header).substitute(vvars), file=self.file)
        if self.header:
            print(string.Template(self.header).substitute(vvars), file=self.file)
        print(file=self.file)
        print("`timescale %s" % self.timescale, file=self.file)
        print(file=self.file)

    def writeModuleHeader(self, intf):
        # _writeModuleHeader(self.file, intf, doc)
        # def _writeModuleHeader(f, intf, doc):
        doc = _makeDoc(inspect.getdoc(intf), self.comment)
        print(doc, file=self.file)
        print("module %s (" % intf.name, file=self.file)
        b = StringIO()
        if self.standard == '2005':
            # ANSI-style module declaration
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
                    if s._driven == 'reg':
                        pass
                    else:
                        pass

                    print('    {} {} {} {} {},'.format(d, s.driven, p, r, portname), file=b)

                else:
                    print('    input {} {} {},'.format(p, r, portname), file=b)
                    if not s._read:
                        warnings.warn("%s: %s" % (_error.UnusedPort, portname),
                                      category=ToVerilogWarning
                                      )

            print(b.getvalue()[:-2], file=self.file)
            b.close()
            print(");", file=self.file)
            print(file=self.file)

        else:
            for portname in intf.argnames:
                print("    %s," % portname, file=b)
            print(b.getvalue()[:-2], file=self.file)
            b.close()
            print(");", file=self.file)
            print(doc, file=self.file)
            print(file=self.file)
            for portname in intf.argnames:
                s = intf.argdict[portname]
                if s._name is None:
                    raise ToVerilogError(_error.ShadowingSignal, portname)
                if s._inList:
                    raise ToVerilogError(_error.PortInList, portname)
                # make sure signal name is equal to its port name
                s._name = portname
                r = _getRangeString(s)
                p = _getSignString(s)
                if s._driven:
                    if isinstance(s, _TristateSignal):
                        print("inout %s%s%s;" % (p, r, portname), file=self.file)
                    else:
                        print("output %s%s%s;" % (p, r, portname), file=self.file)
                    if s._driven == 'reg':
                        print("reg %s%s%s;" % (p, r, portname), file=self.file)
                    else:
                        print("wire %s%s%s;" % (p, r, portname), file=self.file)
                else:
                    if not s._read:
                        warnings.warn("%s: %s" % (_error.UnusedPort, portname),
                                      category=ToVerilogWarning
                                      )
                    print("input %s%s%s;" % (p, r, portname), file=self.file)
            print(file=self.file)

    def writeSigDecls(self, intf, siglist, memlist):
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
                    warnings.warn("%s: %s" % (_error.UnreadSignal, s._name),
                                  category=ToVerilogWarning
                                  )
                k = 'wire'
                if s._driven == 'reg':
                    k = 'reg'
                # the following line implements initial value assignments
                # don't initial value "wire", inital assignment to a wire
                # equates to a continuous assignment [reference]
                if not self.initial_values or k == 'wire':
                    print("%s %s%s%s;" % (k, p, r, s._name), file=self.file)
                else:
                    if isinstance(s._init, EnumItemType):
                        print("%s %s%s%s = %s;" %
                              (k, p, r, s._name, s._init._toVerilog()), file=self.file)
                    else:
                        print("%s %s%s%s = %s;" %
                              (k, p, r, s._name, _intRepr(s._init)), file=self.file)
            elif s._read:
                if isinstance(s, Constant):
                    c = int(s.val)
                    c_len = s._nrbits
                    c_str = "%s" % c
                    print("localparam %s%s = %s'd%s;" % (r, s._name, c_len, c_str), file=self.file)
                else:
                    # the original exception
                    # raise ToVerilogError(_error.UndrivenSignal, s._name)
                    # changed to a warning and a continuous assignment to a wire
                    warnings.warn("%s: %s" % (_error.UndrivenSignal, s._name),
                                  category=ToVerilogWarning
                                  )
                    constwires.append(s)
                    print("wire %s%s;" % (r, s._name), file=self.file)
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
            k = 'wire'
            initial_assignments = None
            if m._driven:
                k = m._driven

                if self.initial_values and not k == 'wire':
                    if all([each._init == m.mem[0]._init for each in m.mem]):

                        initialize_block_name = ('INITIALIZE_' + m.name).upper()
                        _initial_assignments = (
                            '''
                            initial begin: %s
                                integer i;
                                for(i=0; i<%d; i=i+1) begin
                                    %s[i] = %s;
                                end
                            end
                            ''' % (initialize_block_name, len(m.mem), m.name,
                                   _intRepr(m.mem[0]._init)))

                        initial_assignments = (
                            textwrap.dedent(_initial_assignments))

                    else:
                        val_assignments = '\n'.join(
                            ['    %s[%d] <= %s;' %
                             (m.name, n, _intRepr(each._init))
                             for n, each in enumerate(m.mem)])
                        initial_assignments = (
                            'initial begin\n' + val_assignments + '\nend')
                print("%s %s%s%s [0:%s-1];" % (k, p, r, m.name, m.depth), file=self.file)
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
                print('reg {}{} {} [0:{}-1];'.format(p, r, m.name, m.depth), file=self.file)
                val_assignments = '\n'.join(
                            ['    %s[%d] <= %s;' %
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
            c_str = "%s" % c
            print("assign %s = %s'd%s;" % (s._name, c_len, c_str), file=self.file)
        # print(file=self.file)

        # shadow signal assignments
        for s in siglist:
            if hasattr(s, 'toVerilog') and s._driven:
                print(s.toVerilog(), file=self.file)
        print(file=self.file)

    def writeModuleFooter(self):
        print("endmodule", file=self.file)

    def writeDoc(self, node):
        assert hasattr(node, 'doc')
        doc = _makeDoc(node.doc, '// ', self.ind)
        print(doc, file=self.file)

    def writeAlwaysHeader(self, tree):
        assert tree.senslist
        senslist = tree.senslist
        print("always ", end='', file=self.file)
        self.writeSensitivityList(senslist)
        print(" begin: %s" % tree.name, file=self.file)
        self.indent()

    def writeSensitivityList(self, senslist):
        ic(self.__class__.__name__, senslist)
        # sep = ', '
        # print("@(", file=self.file)
        # for e in senslist[:-1]:
        #     print(e._toVerilog() + sep, file=self.file)
        #     # print(sep, file=self.file)
        # print(senslist[-1]._toVerilog(), file=self.file)
        # print(")", file=self.file)
        ss = []
        for e in senslist:
            ss.append(e._toVerilog())

        print("@({})".format(','.join(ss)), end='', file=self.file)

    def writeDeclarations(self, tree):
        for name, obj in tree.vardict.items():
            print(file=self.file)
            self.writeDeclaration(obj, name, "reg")

    def writeDeclaration(self, obj, name, direction):
        if direction:
            direction = direction + ' '
        if type(obj) is bool:
            print("%s%s" % (direction, name), end='', file=self.file)
        elif isinstance(obj, int):
            if direction == "input ":
                print("input %s;" % name, end='', file=self.file)
                print(file=self.file)
            print("integer %s" % name, end='', file=self.file)
        elif isinstance(obj, _Ram):
            print("reg [%s-1:0] %s [0:%s-1]" % (obj.elObj._nrbits, name, obj.depth), end='', file=self.file)
        elif hasattr(obj, '_nrbits'):
            s = ""
            if isinstance(obj, (intbv, _Signal)):
                if obj._min is not None and obj._min < 0:
                    s = "signed "
            print("%s%s[%s-1:0] %s" % (direction, s, obj._nrbits, name), end='', file=self.file)
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
            print(" = %s;" % inival, end='', file=self.file)
        else:
            print(";", end='', file=self.file)

    def writefile(self, h, intf, doc, siglist, memlist, genlist):
        self.file.close()

    def indent(self):
        self.ind += ' ' * 4

    def dedent(self):
        self.ind = self.ind[:-4]

    def emitline(self):
        ''' process the current self.ir list '''
        print('// {}'.format(self.ir), file=self.file)
        del self.ir[:]

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


myhdl_header = """\
// File: $filename
// Generated by MyHDL $version
// Date: $date
"""


def _writeTestBench(f, intf, trace=False):
    print("module tb_%s;" % intf.name, file=f)
    print(file=f)
    fr = StringIO()
    to = StringIO()
    pm = StringIO()
    for portname in intf.argnames:
        s = intf.argdict[portname]
        r = _getRangeString(s)
        if s._driven:
            print("wire %s%s;" % (r, portname), file=f)
            print("        %s," % portname, file=to)
        else:
            print("reg %s%s;" % (r, portname), file=f)
            print("        %s," % portname, file=fr)
        print("    %s," % portname, file=pm)
    print(file=f)
    print("initial begin", file=f)
    if trace:
        print('    $dumpfile("%s.vcd");' % intf.name, file=f)
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
    print("%s dut(" % intf.name, file=f)
    print(pm.getvalue()[:-2], file=f)
    print(");", file=f)
    print(file=f)
    print("endmodule", file=f)


def _getRangeString(s):
    if s._type is bool:
        return ''
    elif s._nrbits is not None:
        nrbits = s._nrbits
        return "[%s:0] " % (nrbits - 1)
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
    r = "%s%s%s" % (size, radix, num)
    if n < 0:  # add brackets and sign on negative numbers
        r = "(-%s)" % r
    return r


if __name__ == '__main__':
    pass

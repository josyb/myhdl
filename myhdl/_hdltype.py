#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2020 Jan Decaluwe
#  Copyright (C) 2020 Josy Boelen
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

'''
Created on 1 jan. 2020

@author: josy
'''

from abc import ABC, abstractmethod
from copy import deepcopy


class hdltype(ABC):
    ''' the (newly introduced) base type to derive all MyHDL types from '''

    def __init__(self, val=None):
        self._init = deepcopy(val)
        self._val = deepcopy(val)
        self._next = deepcopy(val)
        self._name = None
        self._driven = None
        self._read = False
        self._used = False
        self._nrbits = None

    @property
    @abstractmethod
    def val(self):
        pass

    @property
    @abstractmethod
    def nbits(self):
        pass

    @property
    @abstractmethod
    def next(self):
        ''' a place holder (does not need to be overridden?)'''
        pass
#         raise AttributeError('the .next attribute is write only; i.o.w. it is only used at the left hand of the assignment')

    @next.setter
    @abstractmethod
    def next(self, value):
        pass

    @abstractmethod
    def _update(self):
        pass

    @abstractmethod
    def _clear(self):
        pass

#     @abstractmethod
#     def toHDL(self, hdl):
#         '''
#             handle the name for all convertors
#             hdl: currently 'VHDL' or 'Verilog'
#         '''
#         pass

    # 'static' methods (that are not to be overridden, unless ...)
    # support for the 'driven' attribute
    @property
    def driven(self):
        return self._driven

    @driven.setter
    def driven(self, val):
        if not val in ("reg", "wire", True):
            raise ValueError('Expected value "reg", "wire", or True, got "%s"' % val)
        self._driven = val

    # support for the 'read' attribute
    @property
    def read(self):
        return self._read

    @read.setter
    def read(self, val):
        if not val in (True,):
            raise ValueError('Expected value True, got "%s"' % val)
        self._read = True

#     def _markRead(self):
#         self._read = True

    # support for the 'used' attribute
    @property
    def used (self):
        return self._used

    # 'used' attribute
    def _markUsed(self):
        self._used = True


if __name__ == '__main__':
    pass

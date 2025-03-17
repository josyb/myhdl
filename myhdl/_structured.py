'''
Created on 10 mrt. 2025

inspired by previous work starting in 2015
@author: josy
'''
#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2003-2016 Jan Decaluwe
#  Enhanced 2015-2025 Josy Boelen
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

import math

from myhdl._Signal import _isListOfSigs, _Signal
from myhdl._simulator import _siglist


# helper function for both Array and (future) StructType
def setnext(obj, value):
    '''
        a local function to do the work, recursively
        handles both Array and StructType
    '''
    if isinstance(obj, (list, Array)):
        # recurse
        if isinstance(value, int):
            for i, item in enumerate(obj):
                setnext(item, value)
        else:
            for i, item in enumerate(obj):
                setnext(item, value[i])
    # elif isinstance(obj, StructType):
    #     if isinstance(value, StructType):
    #         # assume the objects are of the same type ...
    #         dests = vars(obj)
    #         srcs = vars(value)
    #         for key in dests:
    #             setnext(dests[key], srcs[key])
    #     else:
    #         # the values are a collection of integers...
    #         # use the sequencelist to enumerate the value
    #         idx = 0
    #         for key in obj.sequencelist:
    #             if hasattr(obj, key):
    #                 setnext(vars(obj)[key], value[idx])
    #                 idx += 1

    elif isinstance(obj, _Signal):
        if isinstance(value, _Signal):
            obj._setNextVal(value.val)
        else:
            obj._setNextVal(value)


class Array(object):
    '''
        it would be better if we could derive this from a
        a (base) MyHDLobject
        because we then could inherit the basic behaviour
        
        10-03-205: initially we want to restrict this to be an alternative to the list of Signals
        later we will accept StructType, and Array itself ...
    '''

    def __init__(self, *args):
        '''
            we allow for many ways to instantiate an Array object
            1) encapsulate a 'default' ListOfSignals 
                a = Array([Signal(intbv(0)[W:]) for __ in range(N)])
                this is maynli a work-around to make migration easier
            2) the preferred way is to define an Array by it's shape and element type
               (kind like numpy arrays)
               b = Array(shape, element)
               with shape: a tuple of dimensions, 3 maximum!
               and element: a MyHDLobject , Signal, intbv, ...
        '''
        self._name = None
        self._driven = None
        self._driver = None
        self._read = False
        self._readers = []
        self._used = False

        self._shape = None
        self._size = None
        self._dtype = None
        self._array = None

        self._slicesigs = []

        if len(args) == 2:
            # shape
            if isinstance(args[0], int):
                self._shape = (args[0],)
                self._size = args[0]

            elif isinstance(args[0], tuple):
                for n in args[0]:
                    assert isinstance(n, int)

                assert len(args[0]) <= 3
                self._shape = args[0]
                self._size = math.prod(args[0])
            else:
                raise ValueError(f'Array: Only handle single `int` or `tuple` of `int` as shape specification')

            # _dtype
            assert isinstance(args[1], _Signal)  # later add StructType etc
            self._dtype = args[1]
            # we build it
            # create a list of list of ..
            # this let's us delegate indexing and slicing to Python's methods
            if len(self._shape) == 3:
                self._array = [[[self._dtype.duplicate()
                                 for __ in range(self.shape[2])]
                                 for __ in range(self.shape[1])]
                                 for __ in range(self.shape[0])]
            elif len(self._shape) == 2:
                self._array = [[self._dtype.duplicate()
                                for __ in range(self.shape[1])]
                                for __ in range(self.shape[0])]
            else:
                self._array = [self._dtype.duplicate()
                               for __ in range(self.shape[0])]

        elif _isListOfSigs(args[0]):
            # wrap it in a nicer package :)
            self._shape = (len(args[0]),)
            self._size = len(args[0])
            self._dtype = args[0][0]
            self._array = args[0]

        else:
            raise ValueError(f'Can not create Array with {args}')

    @property
    def _info(self):
        return f'{repr(self)} used {self._used}, driven {self._driven}, driver {self._driver}, read {self._read}, readers {self._readers} '

    def __str__(self):
        if self._name:
            return self._name
        else:
            return str(self._array)

    def __repr__(self):
        rval = f'Array{self._shape} of {repr(self._dtype)}'
        if self._name:
            return self._name + '= ' + rval
        else:
            return rval

    def duplicate(self):
        return Array(self._shape, self._dtype)

    def _clear(self):
        pass

    # length
    # same behaviour as for multi-dimensional lists
    # it returns the highest rank
    def __len__(self):
        return len(self._array)

    @property
    def shape(self):
        return self._shape

    @property
    def size(self):
        return self._size

    def _update(self):

        def collectwaiters(obj, waiterlist):
            ''' a local recursive function to collect the 'waiters' '''
            if isinstance(obj[0], (list, Array)):
                for item in obj:
                    collectwaiters(item, waiterlist)
            else:
                for item in obj:
                    waiterlist.extend(item._update())

        # delegate to Signal
        # collect the waiters for all Signals in the current Array
        waiterlist = []
        collectwaiters(self, waiterlist)
        return waiterlist

    # support for the 'next' attribute
    @property
    def next(self):
        # this is only a placeholder?
        pass

    @next.setter
    def next(self, val):
        if isinstance(val, Array):
            self._setNextVal(val._array)
            _siglist.append(self)
        elif isinstance(val, list):
            self._setNextVal(val)
            _siglist.append(self)
        elif isinstance(val, tuple):
            # assume only one level of depth for now
            idxl = 0
            idxh = 0
            for subval in val:
                if isinstance(subval, Array):
                    #                     trace.print('Array', repr(subval))
                    idxh += len(subval)
                    dst = self[idxl:idxh]
                    setnext(dst, subval._array)
                    idxl = idxh
                    _siglist.append(dst)
                elif isinstance(subval, _Signal):
                    # Signal or SructType
                    setnext(self[idxh], subval)
                    idxh += 1
                    idxl = idxh
                elif isinstance(subval, int):
                    # must infer size?
                    setnext(self[idxh], subval)
                    idxh += 1
                    idxl = idxh
#                     raise ValueError('Array .next: don\'t handle integer in tuple')
                elif isinstance(subval, tuple):
                    raise ValueError('Array .next: don\'t handle tuple(s) in tuple')
                else:
                    raise ValueError('Array .next: Tuple: not handled: {}'.format(repr(subval)))
            _siglist.append(self)
        elif isinstance(val, int):
            # setting all elements to the same value
            # mostly used to set everything to 0
            # it will auto-recurse ...?
            # this will simulate. but take extra work for the conversion
            # as we may need a nested (others => (others => ...))
            for ele in self._array:
                ele._setNextVal(val)

    def _setNextVal(self, val):
        setnext(self, val)

    # support for the 'driven' attribute
    @property
    def driven(self):

        def ldriven(obj):
            ''' a local function to do the work, recursively '''
            if not hasattr(self._dtype, '_driven'):
                return False

            if isinstance(obj[0], (list, Array)):
                for item in obj:
                    if ldriven(item):
                        return True
            else:
                # lowest level
                for item in obj:
                    if item._driven:
                        return True
                return False

        r = self._driven or ldriven(self)
#         print(r)
        return r

    @driven.setter
    def driven(self, val):
#         print('setting ({}).driven to {}'.format(self, val))
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
        self._markRead()

    def _markRead(self):
        self._read = True

    # 'used' attribute
    def _markUsed(self):
        self._used = True

    def __getitem__(self, key):
        # delegate to Python's list
        # TODO:
        # note that this either returns a list of ListofSignals, a ListofSignals or a single Signal (rahter object)
        # this complicates forwarding parts of an array to a sub-module
        # perhaps we have to create ShadowArrays?
        return self._array[key]

    def __setitem__(self, key, val):
        raise TypeError("Array object doesn't support item/slice assignment")

# TODO: do we need ShadowArray?
#     ### use call interface for shadow signals ###
#     def __call__(self, left, right=None):
#         if right is None and len(self._shape) == 1:
#             # it is a (final) index and we can return the addressed Signal
#             return self[left]
#         else:
#             s = _ShadowArray(self, left, right)
#             self._slicesigs.append(s)
#             return s
#
#
# class _ShadowArray(Array):
#
#     def __init__(self, array, left=None, right=None):
#         self._parent = array

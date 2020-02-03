'''
Created on 12 May 2019

@author: josy
'''
from myhdl import  intbv
# from myhdl._compat import integer_types


class Parameter(object):
    ''' 
        a wrapper class around the Parameter 
        which later can be properly recognized by the converter
    '''

    def __init__(self, val):
        self._val = val
        self._nrbits = None
        self._min = None
        self._max = None
        if isinstance(val, bool):
            self._type = bool
            self._nrbits = 1
        elif isinstance(val, int):
            self._type = int
        elif isinstance(val, intbv):
            self._type = intbv
            self._min = val._min
            self._max = val._max
            self._nrbits = val._nrbits
        else:
            self._type = type(val)
            if hasattr(val, '_nrbits'):
                self._nrbits = val._nrbits

    def __str__(self):
        if isinstance(self._val, intbv):
            return "{}".format(self._val._val)
        else:
            return "{}".format(self._val)

    def __repr__(self):
        if isinstance(self._val, intbv):
            return "Parameter({})".format(self._val._val)
        else:
            return "Parameter({})".format(self._val)

    @property
    def Value(self):
        if isinstance(self._val, intbv):
            return self._val._val
        else:
            return self._val


# for export
ParameterType = Parameter

if __name__ == '__main__':
    pass

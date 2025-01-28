'''
Created on 3 dec. 2024

@author: josy
'''

import inspect

from abc import ABC, abstractmethod

try:
    from icecream import ic
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

# from myhdl import block
from myhdl._Signal import _Signal


class HdlClass(ABC):
    '''
        This Abstract Base Class 
    '''

    @abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    # @block
    def hdl(self, *args, **kwargs):
        ''' 
            placeholder for user written hdl 
            
            !!! do not forget the `@block` !!!
            Note that even if you set skipname=True as the block argument eventually
            a name will be given to that block; either by yourself or in the better case
            by the hdlinstances() method below
        '''
        pass

    def convert(self, **kwargs):
        '''
            direct conversion of the top level class
            without having to write a `wrapper`
            
            the converter expects a _Block object
            so we run the `hdl()` method            
        '''
        if hasattr(self, '_hdlblock'):
            # reset _driven attribute to avoid a '*Signal has multiple drivers: *' **fatal** error
            # when converting for successive V* (as shown in test_hdlclassxx.py
            # TODO: what about lower levels?
            for arg in self._hdlb.args:
                if isinstance(arg, _Signal):
                    arg._driven = False
        else:
            self._hdlblock = self.hdl()

        ic(self, kwargs)
        self._hdlblock.convert(**kwargs)

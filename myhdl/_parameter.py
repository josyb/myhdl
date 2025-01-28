'''
Created on 20 jan. 2025

@author: josy
'''

from myhdl._Signal import Constant


class Parameter(Constant):

    def __init__(self, val=None):
        if isinstance(val, Parameter):
            super(Parameter, self).__init__(val.value)
            self.parent = val
        else:
            super(Parameter, self).__init__(val)
            self.parent = None

    # override some essentials
    def __repr__(self):
        if self._name:
            return f"{self._name} = Parameter({repr(self._val)})"
        else:
            return f"Parameter({repr(self._val)})"

    @property
    def value(self):
        return self._val


if __name__ == '__main__':
    pass

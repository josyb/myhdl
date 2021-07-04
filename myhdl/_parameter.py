'''
Created on 4 jul. 2021

@author: josy
'''


class Parameter(object):

    def __init__(self, name, value):
        self.name = name
        self._value = value

    @property
    def value(self):
        if isinstance(self._value, int):
            return self._value

    def __repr__(self):
        return 'Parameter({}, {})'.format(self.name, self._value)

    def __str__(self):
        return '{}'.format(self.name)

    def __int__(self):
        return self._value


if __name__ == '__main__':
    pass

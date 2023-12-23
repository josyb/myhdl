'''
Created on 29 okt. 2023

@author: josy
'''
import os

from icecream import ic
ic.configureOutput(argToStringFunction=str, outputFunction=print, includeContext=True, contextAbsPath=True)


class VhdlWriter(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            ic("{0} = {1}".format(key, value))

    def openfile(self, name, directory):
        filename = name + ".vhd"
        path = os.path.join(directory, filename)
        setattr(self, 'file', open(path, 'w'))


if __name__ == '__main__':
    pass

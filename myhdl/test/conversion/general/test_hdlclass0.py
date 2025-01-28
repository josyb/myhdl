'''
Created on 21 dec. 2024

@author: josy
'''

from myhdl import HdlClass, block, Signal, always_comb


class Minimal(HdlClass):
    ''' a minimal class design to exercise/debug the conversion flow '''

    def __init__(self, Sigin, SigOut=None):
        self.Sigin = Sigin
        self.SigOut = SigOut if SigOut is not None else Sigin.duplicate()

    @block(skipname=False)
    def hdl(self):

        @always_comb
        def comb():
            self.SigOut.next = ~self.Sigin

        # loi = self.hdlinstances()
        # print(f'{loi=}')
        #
        # return loi
        return comb


if __name__ == '__main__':
    if 1:
        Sigin = Signal(bool(0))
        SigOut = Signal(bool(0))

        # dfc = Minimal(Sigin, SigOut)
        dfc = Minimal(Sigin)
        dfc.convert(hdl='Verilog', hierarchical=-1, name='Minimal')
        # dfc.convert(hdl='VHDL', name='Minimal')

    else:

        def convert():
            Sigin = Signal(bool(0))
            SigOut = Signal(bool(0))

            dfc = Minimal(Sigin)
            # dfc.convert(hdl='VHDL', name='Minimal')
            # dfc.convert(hdl='Verilog', name='Minimal')

        convert()

'''
Created on 3 dec. 2024

@author: josy
'''

from myhdl import (HdlClass, Signal, intbv, block, always_seq, OpenPort, always_comb,
                   Constant)


class UpCounter(HdlClass):

    def __init__(self, RANGE, Clk, Reset, SClr, CntEn, Q=None, IsMax=None, WRAP_AROUND=False):
        '''
            RANGE: int : number of counts
            Clk: Signal(bool()): the domain clock
            Reset: ResetSignal(): its associated reset
            SClr: Signal(bool()): resets the count
            CntEn: Signal(bool()): advances count
            Q: Signal(intbv()[w:]): the actual count
        '''
        self.RANGE = RANGE
        self.Clk = Clk
        self.Reset = Reset
        self.SClr = SClr
        self.CntEn = CntEn
        self.Q = Q if Q is not None else Signal(intbv(0, 0, RANGE))
        self.IsMax = IsMax if IsMax is not None else Signal(bool(0))
        self.WRAP_AROUND = WRAP_AROUND

    @block
    def hdl(self):
        count = Signal(intbv(0, 0, self.RANGE))

        if self.WRAP_AROUND:

            @always_seq(self.Clk.posedge, reset=self.Reset)
            def synch():
                if self.SClr or self.CntEn:
                    if self.SClr:
                        count.next = 0
                    else:
                        if count < (self.RANGE - 1):
                            count.next = count + 1
                        else:
                            count.next = 0

        else:

            @always_seq(self.Clk.posedge, reset=self.Reset)
            def synch():
                if self.SClr or self.CntEn:
                    if self.SClr:
                        count.next = 0
                    else:
                        if count < (self.RANGE - 1):
                            count.next = count + 1

        @always_comb
        def comb():
            self.IsMax.next = (count == self.RANGE - 1)
            self.Q.next = count

        print('UpCounter')
        return instances()


class Pwm(HdlClass):

    def __init__(self, RANGE, Clk, Reset, PwmValue, PwmOut=None):
        self.RANGE = RANGE
        self.Clk = Clk
        self.Reset = Reset
        self.PwmValue = PwmValue
        self.PwmOut = PwmOut if PwmOut is not None else Signal(bool(0))

    @block
    def hdl(self):
        if 1:
            SClr = Constant(bool(0))
            CntEn = Constant(bool(1))
            counter = UpCounter(self.RANGE, self.Clk, self.Reset, SClr, CntEn, IsMax=OpenPort(), WRAP_AROUND=True)
        else:
            counter = UpCounter(self.RANGE, self.Clk, self.Reset, SClr=Constant(bool(0)), CntEn=Constant(bool(1)), IsMax=OpenPort(), WRAP_AROUND=True)

        @always_seq(self.Clk.posedge, reset=self.Reset)
        def synch():
            if counter.Q >= self.PwmValue:
                self.PwmOut.next = 0
            else:
                self.PwmOut.next = 1

        print('PwmCounter')
        return instances()


class XYMotors(HdlClass):

    def __init__(self, PWMCOUNT, Clk, Reset, XSpeed, YSpeed, XDrive, YDrive):
        self.PWMCOUNT = PWMCOUNT
        self.Clk = Clk
        self.Reset = Reset
        self.XSpeed = XSpeed
        self.YSpeed = YSpeed
        self.XDrive = XDrive
        self.YDrive = YDrive

    @block
    def hdl(self):
        xmotor = Pwm(self.PWMCOUNT, self.Clk, self.Reset, self.XSpeed, self.XDrive)
        ymotor = Pwm(self.PWMCOUNT, self.Clk, self.Reset, self.YSpeed, self.YDrive)

        print('XYMotors')
        return instances()


if __name__ == '__main__':

    from myhdl import ResetSignal, instance, delay, StopSimulation, instances

    if 0:

        # create a minimal test-bench to test the .vcd generation
        # as we want/have to weed out the `None` - because of an @block(skipname=True)
        # which add an unnecessary indentation level in the waveform which absolutely looks ugly
        @block
        def tb_xymotors():
            PWMCOUNT = 100
            Clk = Signal(bool(0))
            Reset = ResetSignal(0, 1, False)
            XSpeed = Signal(intbv(0, 0, PWMCOUNT))
            YSpeed = Signal(intbv(0, 0, PWMCOUNT))
            XDrive = Signal(bool(0))
            YDrive = Signal(bool(0))

            dft = XYMotors(PWMCOUNT, Clk, Reset, XSpeed, YSpeed, XDrive, YDrive)
            dfthdl = dft.hdl()
            dfthdl.name = 'XYMotors'

            tCK = 10

            @instance
            def genclkreset():
                Reset.next = 1
                for dummy in range(3):
                    Clk.next = 1
                    yield delay(tCK // 2)
                    Clk.next = 0
                    yield delay(tCK - tCK // 2)

                Clk.next = 1
                yield delay(tCK // 2)
                Clk.next = 0
                Reset.next = 0
                yield delay(tCK - tCK // 2)
                while True:
                    Clk.next = 1
                    yield delay(tCK // 2)
                    Clk.next = 0
                    yield delay(tCK - tCK // 2)

            @instance
            def stimulus():
                for dummy in range(10):
                    yield Clk.posedge

                raise StopSimulation

            return instances()

        dft = tb_xymotors()
        dft.config_sim(trace=True, timescale='1ps', tracebackup=False)
        dft.run_sim()

    def convert():
        # try converting
        # note they will appear in this order in the entity/module declaration; why?
        PWMCOUNT = 100
        Clk = Signal(bool(0))
        Reset = ResetSignal(0, 1, False)
        XSpeed = Signal(intbv(0, 0, PWMCOUNT))
        YSpeed = Signal(intbv(0, 0, PWMCOUNT))
        XDrive = Signal(bool(0))
        YDrive = Signal(bool(0))

        # doing direct conversion from the class instance itself
        # this is quite necessary for hierarchical conversion
        dfc = XYMotors(PWMCOUNT, Clk, Reset, XSpeed, YSpeed, XDrive, YDrive)
        for level in [0]:
            dfc.name = f'xymotors_h{level}'.replace('-', 'm')
            dfc.convert(hdl='Verilog', name=f'xymotors_h{level}'.replace('-', 'm'), hierarchical=level, no_testbench=True)

    convert()

from myhdl import (block, Signal, delay, always, always_comb,
                   instance, StopSimulation, conversion)


class HDLClass(object):

    @block
    def model(self, clock, input_interface, output_interface, message):

        internal_in = Signal(False)
        internal_out = Signal(False)

        @always_comb
        def assignments():
            internal_in.next = input_interface
            output_interface.next = internal_out

        @always(clock.posedge)
        def do_something():
            # print(message)
            print('do_something')
            internal_out.next = internal_in.next

        return do_something, assignments


class InterfaceWithInstanceSignal(object):

    def __init__(self):

        self.internal_ins = [Signal(False) for __ in range(4)]
        self.internal_outs = [Signal(False) for __ in range(4)]

    @block
    def model(self, clock, input_interface, output_interface, index, message):

        internal_in = self.internal_ins[index]
        internal_out = self.internal_outs[index]

        @always_comb
        def assignments():
            internal_in.next = input_interface
            output_interface.next = internal_out

        @always(clock.posedge)
        def do_something():
            # print(message)
            print('do_something')
            internal_out.next = internal_in.next

        return do_something, assignments


@block
def different_class_pipeline(clock, input_interface, output_interface):

    class_inst1 = HDLClass()
    class_inst2 = HDLClass()

    intermediate_interface = Signal(False)

    class_hdl_inst1 = class_inst1.model(clock, input_interface, intermediate_interface, 'message_1')

    class_hdl_inst2 = class_inst2.model(clock, intermediate_interface, output_interface, 'message_2')

    return class_hdl_inst1, class_hdl_inst2


@block
def common_class_pipeline(clock, input_interface, output_interface):

    class_inst = HDLClass()

    intermediate_interface = Signal(False)
    intermediate_interface_2 = Signal(False)
    intermediate_interface_3 = Signal(False)

    class_hdl_inst1 = class_inst.model(clock, input_interface, intermediate_interface, 'message_1')

    class_hdl_inst2 = class_inst.model(clock, intermediate_interface, intermediate_interface_2, 'message_2')

    class_hdl_inst3 = class_inst.model(clock, intermediate_interface_2, intermediate_interface_3, 'message_3')

    class_hdl_inst4 = class_inst.model(clock, intermediate_interface_3, output_interface, 'message_4')

    return class_hdl_inst1, class_hdl_inst2, class_hdl_inst3, class_hdl_inst4


@block
def interface_with_method_pipeline(clock, input_interface, output_interface):

    class_inst = InterfaceWithInstanceSignal()

    intermediate_interface = Signal(False)
    intermediate_interface_2 = Signal(False)
    intermediate_interface_3 = Signal(False)

    class_hdl_inst1 = class_inst.model(clock, input_interface, intermediate_interface, 0, 'message_1')

    class_hdl_inst2 = class_inst.model(clock, intermediate_interface, intermediate_interface_2, 1, 'message_2')

    class_hdl_inst3 = class_inst.model(clock, intermediate_interface_2, intermediate_interface_3, 2, 'message_3')

    class_hdl_inst4 = class_inst.model(clock, intermediate_interface_3, output_interface, 3, 'message_4')

    return class_hdl_inst1, class_hdl_inst2, class_hdl_inst3, class_hdl_inst4


@block
def bench(class_name='different_class'):

    clk = Signal(False)
    input_interface = Signal(False)
    output_interface = Signal(False)

    N = 20

    @instance
    def clkgen():

        clk.next = 0
        for __ in range(N):
            yield delay(10)
            clk.next = not clk

        raise StopSimulation()

    if class_name == 'common_class':
        pipeline_inst = common_class_pipeline(clk, input_interface, output_interface)

    elif class_name == 'interface':
        pipeline_inst = interface_with_method_pipeline(clk, input_interface, output_interface)

    elif class_name == 'different_class':
        pipeline_inst = different_class_pipeline(clk, input_interface, output_interface)

    return pipeline_inst, clkgen


def test_multiple_class_single_method():
    assert conversion.verify(bench()) == 0


def test_single_class_single_method():
    assert conversion.verify(bench(class_name='common_class')) == 0


def test_single_interface_with_single_method():
    assert conversion.verify(bench(class_name='interface')) == 0


if __name__ == '__main__':
    dfc = bench(class_name='interface')
    # dfc.config_sim(trace=True)
    # dfc.run_sim()
    dfc.convert(hdl='VHDL')

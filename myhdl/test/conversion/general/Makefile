all:  ghdl iverilog sverilog 

ghdl:
	py.test --sim ghdl

vlog:
	py.test --sim vlog

vcom:
	py.test --sim vcom

iverilog:
	py.test --sim iverilog

sverilog:
	py.test --sim sverilog

cver:
	py.test --sim cver

clean:
	- rm *.o *.out *.v *.vhd *.sv *.hex *.pyc *~ *.vcd* *.log *_ghdl

gitclean:
	git clean -dfx

package myhdl_pkg;

	//	// This is a function that calculated the ceil(log2(x)) for any integer x
	//	function automatic int clog2(input value);
	//		int r;
	//		begin
	//			value = value - 1;
	//			for (r = 0; value > 0; r = r + 1) value = value >> 1;
	//			return r;
	//		end
	//	endfunction

	function automatic int widthr(input int value);
		// this function calculates the number of bits need to represent
		// the given `value` in a binary code
		// 7 will result in a return value of 3
		// but 8 will return a width 0f 4
		int r;
		int tval;
		begin
			if (value < 0) begin
				tval = -value;
				r = 1;
			end
			else begin
				tval = value;
				r = 0;
			end
			for (; tval > 0; r = r + 1 ) tval = tval >> 1;
			return r;
		end
	endfunction

	function automatic int widthu(input int value);
		// this function calculates the number of bits need to binary encode
		// the  number of  states specified by `value`
		// both 7 and 8 will result in a return value of 3
		int r;
		int tval;
		begin
			if (value < 0) begin
				tval = -value;
				r = 1;
			end
			else begin
				tval = value;
				r = 0;
			end
			tval = tval - 1; // making sure that powers of 2 are stepped down 1 bit	
			for (; tval > 0; r = r + 1 ) tval = tval >> 1;
			return r;
		end
	endfunction


endpackage: myhdl_pkg

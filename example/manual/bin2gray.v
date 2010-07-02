// File: bin2gray.v
// Generated by MyHDL 0.7dev
// Date: Fri Jul  2 13:23:50 2010


`timescale 1ns/10ps

module bin2gray (
    B,
    G
);
// Gray encoder.
// 
// B -- input intbv signal, binary encoded
// G -- output intbv signal, gray encoded
// width -- bit width

input [7:0] B;
output [7:0] G;
reg [7:0] G;






always @(B) begin: BIN2GRAY_LOGIC
    integer i;
    reg [9-1:0] Bext;
    Bext = 9'h0;
    Bext = B;
    for (i=0; i<8; i=i+1) begin
        G[i] <= (Bext[(i + 1)] ^ Bext[i]);
    end
end

endmodule

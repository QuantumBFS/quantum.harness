module mystery_a(
    input  [7:0] x,
    input  [7:0] y,
    output [8:0] z
);
    assign z = x + y;
endmodule

module mystery_b(
    input  [6:0] x,
    input  [6:0] y,
    output [6:0] z
);
    assign z = (x >= y) ? (x - y) : (y - x);
endmodule

module mystery_c(
    input  [5:0] x,
    input  [5:0] y,
    output [11:0] z
);
    assign z = x * y;
endmodule

module mystery_c_karatsuba(
    input  [5:0] x,
    input  [5:0] y,
    output [11:0] z
);
    wire [2:0] x_low = x[2:0];
    wire [2:0] x_high = x[5:3];
    wire [2:0] y_low = y[2:0];
    wire [2:0] y_high = y[5:3];
    wire [5:0] low_product = x_low * y_low;
    wire [5:0] high_product = x_high * y_high;
    wire [3:0] x_sum = x_low + x_high;
    wire [3:0] y_sum = y_low + y_high;
    wire [7:0] sum_product = x_sum * y_sum;
    wire [7:0] cross_product =
        sum_product - {2'b00, low_product} - {2'b00, high_product};
    assign z =
        {6'b000000, low_product}
        + ({4'b0000, cross_product} << 3)
        + ({6'b000000, high_product} << 6);
endmodule

module mystery_d(
    input  [4:0] x,
    input  [4:0] y,
    output [10:0] z
);
    wire [9:0] x_squared = x * x;
    wire [9:0] y_squared = y * y;
    assign z = {1'b0, x_squared} + {1'b0, y_squared};
endmodule

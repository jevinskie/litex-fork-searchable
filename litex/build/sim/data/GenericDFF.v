
module GenericDFF
    (
        input d,
        input clk,
        input r,
        input s,
        output reg q
    );

    always @ (posedge clk or posedge r or posedge s)
        if (s)
            q <= 1;
        else if (r)
            q <= 0;
        else
            q <= d;

endmodule


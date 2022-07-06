`timescale 1ns/1ps

module sim_clocker #(
    parameter freq_hz = 1000000,
    parameter phase_deg = 0
)(
    output reg clk
);

localparam clk_per = 1000000000.0 / freq_hz;
localparam phase_delay = clk_per * (phase_deg / 360.0);

initial begin
    $display("pre clk t0 t: %0d", $time);
    clk <= 0;
    $display("post clk t0 t: %0d", $time);
    #(clk_per / 2.0 + phase_delay);
    $display("post phase delay t: %0d", $time);
    forever begin
        $display("pre clk dly t: %0d", $time);
        #(clk_per / 2.0);
        $display("pre clk t: %0d", $time);
        clk <= ~clk;
        $display("post clk t: %0d", $time);
    end
end

endmodule

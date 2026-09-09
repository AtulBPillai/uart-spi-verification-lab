// UART 8N1 transmitter. Data is accepted on valid && ready at the clock edge.
module uart_tx #(
    parameter integer CLKS_PER_BIT = 16
) (
    input wire clk, input wire rst,
    input wire valid, input wire [7:0] data,
    output wire ready, output wire tx,
    output reg busy, output reg done
);
    localparam integer TW = (CLKS_PER_BIT > 1) ? $clog2(CLKS_PER_BIT) : 1;
    reg [TW-1:0] timer;
    reg [3:0] bit_index;
    reg [9:0] frame;
    assign ready = !busy && !rst;
    assign tx = busy ? frame[0] : 1'b1;
    always @(posedge clk) begin
        if (rst) begin
            timer <= 0; bit_index <= 0; frame <= 10'h3ff;
            busy <= 0; done <= 0;
        end else begin
            done <= 0;
            if (valid && ready) begin
                frame <= {1'b1, data, 1'b0};
                timer <= CLKS_PER_BIT - 1;
                bit_index <= 0;
                busy <= 1;
            end else if (busy) begin
                if (timer == 0) begin
                    timer <= CLKS_PER_BIT - 1;
                    if (bit_index == 9) begin
                        busy <= 0; done <= 1;
                    end else begin
                        frame <= {1'b1, frame[9:1]};
                        bit_index <= bit_index + 1'b1;
                    end
                end else timer <= timer - 1'b1;
            end
        end
    end
endmodule

// UART 8N1 receiver: two-flop synchronization, midpoint sampling, one-cycle events.
// CLKS_PER_BIT >= 8. No FIFO or receive backpressure. Synchronous active-high reset.
module uart_rx #(
    parameter integer CLKS_PER_BIT = 16
) (
    input wire clk, input wire rst, input wire rx,
    output reg [7:0] data, output reg valid, output reg framing_error,
    output wire busy
);
    localparam integer TW = (CLKS_PER_BIT > 1) ? $clog2(CLKS_PER_BIT) : 1;
    localparam [2:0] IDLE=0, START=1, DATA=2, STOP=3, WAIT_HIGH=4;
    reg [2:0] state;
    (* ASYNC_REG = "TRUE" *) reg rx_meta, rx_sync;
    reg [TW-1:0] timer;
    reg [2:0] bit_index;
    reg [7:0] shift;
    assign busy = (state != IDLE);
    always @(posedge clk) begin
        if (rst) begin rx_meta <= 1; rx_sync <= 1; end
        else begin rx_meta <= rx; rx_sync <= rx_meta; end
    end
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; timer <= 0; bit_index <= 0; shift <= 0;
            data <= 0; valid <= 0; framing_error <= 0;
        end else begin
            valid <= 0; framing_error <= 0;
            case (state)
                IDLE: if (!rx_sync) begin
                    timer <= CLKS_PER_BIT/2 - 1; state <= START;
                end
                START: if (timer != 0) timer <= timer - 1'b1;
                else if (!rx_sync) begin
                    timer <= CLKS_PER_BIT - 1; bit_index <= 0; state <= DATA;
                end else state <= IDLE;
                DATA: if (timer != 0) timer <= timer - 1'b1;
                else begin
                    shift[bit_index] <= rx_sync;
                    timer <= CLKS_PER_BIT - 1;
                    if (bit_index == 7) state <= STOP;
                    else bit_index <= bit_index + 1'b1;
                end
                STOP: if (timer != 0) timer <= timer - 1'b1;
                else begin
                    if (rx_sync) begin data <= shift; valid <= 1; state <= IDLE; end
                    else begin framing_error <= 1; state <= WAIT_HIGH; end
                end
                WAIT_HIGH: if (rx_sync) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule

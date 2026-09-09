// Eight-bit, MSB-first, full-duplex SPI controller. One CS per byte, modes 0-3.
// All logic uses clk plus enables; SCK is an output, never an internal clock.
module spi_master (
    input wire clk, input wire rst, input wire valid,
    input wire [7:0] tx_data, input wire miso,
    input wire cpol, input wire cpha, input wire [15:0] half_period,
    output wire ready, output reg busy, output reg done, output reg config_error,
    output reg sck, output reg mosi, output reg cs_n, output reg [7:0] rx_data
);
    reg pol, phase, finishing;
    reg [15:0] divider, timer;
    reg [4:0] edge_count;
    reg [7:0] tx_shift, rx_shift;
    wire sample_edge = phase ? edge_count[0] : !edge_count[0];
    assign ready = !busy && !rst;
    always @(posedge clk) begin
        if (rst) begin
            busy <= 0; done <= 0; config_error <= 0;
            sck <= 0; mosi <= 0; cs_n <= 1; rx_data <= 0;
            pol <= 0; phase <= 0; finishing <= 0;
            divider <= 2; timer <= 0; edge_count <= 0;
            tx_shift <= 0; rx_shift <= 0;
        end else begin
            done <= 0; config_error <= 0;
            if (valid && ready) begin
                if (half_period < 2) begin
                    config_error <= 1;
                end else begin
                    pol <= cpol; phase <= cpha;
                    divider <= half_period; timer <= half_period - 1'b1;
                    busy <= 1; cs_n <= 0; sck <= cpol;
                    edge_count <= 0; finishing <= 0; rx_shift <= 0;
                    tx_shift <= cpha ? tx_data : {tx_data[6:0], 1'b0};
                    mosi <= cpha ? 1'b0 : tx_data[7];
                end
            end else if (busy) begin
                if (timer != 0) timer <= timer - 1'b1;
                else begin
                    timer <= divider - 1'b1;
                    if (finishing) begin
                        busy <= 0; cs_n <= 1; done <= 1;
                        rx_data <= rx_shift; sck <= pol;
                    end else begin
                        sck <= !sck;
                        if (sample_edge) rx_shift <= {rx_shift[6:0], miso};
                        else begin
                            mosi <= tx_shift[7];
                            tx_shift <= {tx_shift[6:0], 1'b0};
                        end
                        if (edge_count == 15) finishing <= 1;
                        else edge_count <= edge_count + 1'b1;
                    end
                end
            end else begin
                sck <= cpol; mosi <= 0;
            end
        end
    end
endmodule

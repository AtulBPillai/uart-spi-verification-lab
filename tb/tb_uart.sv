`timescale 1ns/1ps
module tb_uart;
    parameter integer DIV = 16;
    reg clk=0, rst=1, tx_valid=0, rx_line=1;
    reg [7:0] tx_data=0;
    wire tx_ready, tx_line, tx_busy, tx_done, rx_valid, rx_error, rx_busy;
    wire [7:0] rx_data;
    integer tx_frames=0, rx_frames=0, errors=0, checks=0;
    integer rx_events=0, error_events=0;
    reg [7:0] last_received;
    reg prev_rx_valid=0, prev_error=0, prev_done=0;
    bit smoke, waves;
    reg [255:0] tx_seen=0, rx_seen=0;
    string vcd_path;
    always #5 clk = !clk;
    uart_tx #(.CLKS_PER_BIT(DIV)) u_tx(clk,rst,tx_valid,tx_data,tx_ready,tx_line,tx_busy,tx_done);
    uart_rx #(.CLKS_PER_BIT(DIV)) u_rx(clk,rst,rx_line,rx_data,rx_valid,rx_error,rx_busy);

    task automatic check(input bit condition, input string label);
        checks++;
        if (!condition) $fatal(1,"ASSERTION %s t=%0t",label,$time);
    endtask

    always @(posedge clk) begin
        #1;
        if (!rst) begin
            check(!(rx_valid && prev_rx_valid),"UART RX valid must be one cycle");
            check(!(rx_error && prev_error),"UART framing error must be one cycle");
            check(!(tx_done && prev_done),"UART TX done must be one cycle");
            check(!(rx_valid && rx_error),"RX valid and framing error are exclusive");
            if (rx_valid) begin rx_events++; last_received=rx_data; end
            if (rx_error) error_events++;
        end
        prev_rx_valid=rx_valid; prev_error=rx_error; prev_done=tx_done;
    end

    task automatic reset_dut;
        @(negedge clk); rst=1; tx_valid=0; rx_line=1;
        repeat(3) @(negedge clk);
        check(tx_line===1'b1 && tx_ready===1'b0 && tx_busy===1'b0,"TX reset idle");
        rst=0;
        repeat(4) @(negedge clk);
        check(tx_ready===1'b1 && !rx_busy,"UART ready after reset");
    endtask

    // Reference is the frame definition and clock count, not DUT state/registers.
    task automatic transmit(input reg [7:0] value, input bit busy_probe);
        integer cycle, bit_number;
        reg expected;
        @(negedge clk); tx_data=value; tx_valid=1;
        @(posedge clk); #2;
        check(tx_busy===1'b1 && tx_ready===1'b0,"TX accepted request");
        for(cycle=0;cycle<10*DIV;cycle++) begin
            bit_number=cycle/DIV;
            if(bit_number==0) expected=0;
            else if(bit_number==9) expected=1;
            else expected=value[bit_number-1];
            if(!smoke || cycle% DIV == DIV/2)
                check(tx_line===expected,"TX framing, bit order, and divider");
            if(!smoke) check(tx_busy===1'b1 && tx_done===1'b0,"TX full frame duration");
            @(negedge clk);
            if(busy_probe && cycle>=3*DIV && cycle<3*DIV+2) begin
                tx_data=~value; tx_valid=1;
            end else tx_valid=0;
            @(posedge clk); #2;
        end
        check(tx_done===1'b1 && tx_ready===1'b1 && tx_line===1'b1,"TX completion and stop length");
        tx_seen[value]=1; tx_frames++;
        @(negedge clk);
    endtask

    // Independent serial source; period can differ from the DUT's nominal divider.
    task automatic receive(input reg [7:0] value, input integer bit_ns, input bit good_stop);
        integer b, before_rx, before_error;
        before_rx=rx_events; before_error=error_events;
        rx_line=0; #(bit_ns);
        for(b=0;b<8;b++) begin rx_line=value[b]; #(bit_ns); end
        rx_line=good_stop; #(bit_ns);
        rx_line=1;
        if(good_stop) begin
            check(rx_events==before_rx+1,"RX exactly one byte event");
            check(last_received===value,"RX payload from independent serial source");
            check(error_events==before_error,"RX good frame has no framing error");
            rx_seen[value]=1; rx_frames++;
        end else begin
            check(rx_events==before_rx,"RX bad stop does not produce valid data");
            check(error_events==before_error+1,"RX bad stop raises framing error");
            errors++;
            #(2*DIV*10);
        end
    endtask

    task automatic finish_report;
        $display("RESULT uart div=%0d tx_frames=%0d rx_frames=%0d framing_cases=%0d checks=%0d",DIV,tx_frames,rx_frames,errors,checks);
        $display("COVER uart_tx_bytes %0d 256",$countones(tx_seen));
        $display("COVER uart_rx_bytes %0d 256",$countones(rx_seen));
        $display("VERIFICATION_PASS uart");
        $finish;
    endtask

    integer k, before_rx, before_error;
    initial begin
        smoke=$test$plusargs("SMOKE"); waves=$test$plusargs("WAVES");
        if(DIV<8) $fatal(1,"CONFIG CLKS_PER_BIT must be >=8");
        if($value$plusargs("VCD=%s",vcd_path)) begin $dumpfile(vcd_path); $dumpvars(0,tb_uart); end
        reset_dut();
        if(waves) begin transmit(8'hA6,0); #3; receive(8'h3C,DIV*10,1); finish_report(); end
        if(smoke) begin transmit(8'h00,0); #3; receive(8'h00,DIV*10,1); finish_report(); end
        for(k=0;k<256;k++) transmit(k[7:0],0);
        transmit(8'h96,1);
        $display("COVER uart_busy_request 1 1");
        // All bytes, without inserted idle gaps: a continuous 8N1 receive stream.
        #3;
        for(k=0;k<256;k++) receive(k[7:0],DIV*10,1);
        $display("COVER uart_back_to_back 1 1");
        #(2*DIV*10);
        receive(8'hA6,(DIV*10*98)/100,1);
        #(2*DIV*10);
        receive(8'h69,(DIV*10*102)/100,1);
        $display("COVER uart_period_offsets 2 2");
        #(2*DIV*10); receive(8'h5A,DIV*10,0);
        $display("COVER uart_bad_stop 1 1");
        before_rx=rx_events; before_error=error_events;
        rx_line=0; #(DIV*10/4); rx_line=1; #(12*DIV*10);
        check(rx_events==before_rx && error_events==before_error,"RX rejects short false start");
        $display("COVER uart_false_start 1 1");
        before_rx=rx_events; before_error=error_events;
        rx_line=0; #(30*DIV*10); rx_line=1; #(2*DIV*10);
        check(rx_events==before_rx && error_events==before_error+1,"RX break produces one error then waits for HIGH");
        receive(8'hC3,DIV*10,1);
        $display("COVER uart_break_recovery 1 1");
        // Abort a TX and an RX in progress with synchronous reset.
        @(negedge clk); tx_valid=1; tx_data=8'hA5; rx_line=0;
        repeat(3*DIV) @(negedge clk);
        reset_dut();
        before_rx=rx_events; #(12*DIV*10);
        check(rx_events==before_rx,"Reset abort produces no ghost receive");
        transmit(8'hD2,0); #3; receive(8'h2D,DIV*10,1);
        $display("COVER uart_reset_abort 1 1");
        check(&tx_seen && &rx_seen,"Full byte-value coverage reached");
        finish_report();
    end
    initial begin #20000000; $fatal(1,"ASSERTION global UART watchdog timeout"); end
endmodule

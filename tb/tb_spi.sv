`timescale 1ns/1ps
module tb_spi;
    reg clk=0,rst=1,valid=0,cpol=0,cpha=0,miso=0;
    reg [7:0] tx_data=0;
    reg [15:0] half_period=4;
    wire ready,busy,done,config_error,sck,mosi,cs_n;
    wire [7:0] rx_data;
    reg monitor_active=0, expected_pol=0,expected_phase=0;
    reg [7:0] expected_tx,reply,observed_tx;
    integer expected_half,edges=0,samples=0,checks=0,transfers=0;
    time last_edge,cs_start;
    bit smoke,waves;
    reg previous_done=0;
    reg [255:0] mode_bytes[0:3];
    reg [11:0] mode_dividers=0;
    string vcd_path;
    always #5 clk=!clk;
    spi_master dut(clk,rst,valid,tx_data,miso,cpol,cpha,half_period,ready,busy,done,config_error,sck,mosi,cs_n,rx_data);

    task automatic check(input bit condition,input string label);
        checks++;
        if(!condition) $fatal(1,"ASSERTION %s t=%0t",label,$time);
    endtask

    // Serial target model observes only public pins; no DUT internals.
    always @(negedge cs_n) if(monitor_active) begin
        edges=0; samples=0; observed_tx=0; cs_start=$time; last_edge=$time;
        miso = expected_phase ? 1'b0 : reply[7];
    end
    always @(sck) if(monitor_active && !cs_n && !rst && $time>cs_start) begin
        if(!smoke) check($time-last_edge==expected_half*10,"SPI exact half-period and CS setup");
        last_edge=$time; edges++;
        if((!expected_phase && sck!=expected_pol) || (expected_phase && sck==expected_pol)) begin
            check(samples<8,"SPI no extra sample edge");
            observed_tx[7-samples]=mosi;
            samples++;
        end else begin
            // Target changes MISO after launch edge, giving setup before sample edge.
            #1;
            if(samples<8) miso=reply[7-samples]; else miso=0;
        end
    end
    always @(posedge cs_n) if(monitor_active && !rst) begin
        check(edges==16 && samples==8,"SPI exactly eight full clock cycles");
        check(observed_tx===expected_tx,"SPI target observed correct MOSI bits");
        if(!smoke) check($time-last_edge>=expected_half*10,"SPI CS hold after last edge");
    end
    always @(posedge clk) begin
        #1;
        if(!rst) begin
            check(!(done && previous_done),"SPI done is one cycle");
            if(done) check(cs_n===1'b1 && ready===1'b1,"SPI done means deselected and ready");
        end
        previous_done=done;
    end

    task automatic reset_dut;
        monitor_active=0;
        @(negedge clk); rst=1; valid=0;
        repeat(3) @(negedge clk);
        check(cs_n===1'b1 && busy===1'b0 && sck===1'b0,"SPI reset idle");
        rst=0; repeat(3) @(negedge clk);
    endtask

    task automatic transfer(input integer mode,input integer divider,input reg[7:0] value,input reg[7:0] returned,input bit probe_busy);
        integer cycles;
        @(negedge clk);
        cpol=(mode>>1)&1; cpha=mode&1; half_period=divider; tx_data=value; valid=0;
        expected_pol=cpol; expected_phase=cpha; expected_half=divider;
        expected_tx=value; reply=returned;
        @(negedge clk);
        check(sck===expected_pol && cs_n===1'b1,"SPI idle CPOL");
        monitor_active=1; valid=1;
        @(posedge clk); #2;
        check(busy===1'b1 && cs_n===1'b0,"SPI request acceptance");
        cycles=0;
        while(!done && cycles<20*divider+20) begin
            @(negedge clk);
            if(probe_busy && cycles>=2*divider && cycles<2*divider+2) begin
                valid=1; cpol=!expected_pol; cpha=!expected_phase;
                half_period=divider+3; tx_data=~value;
            end else valid=0;
            @(posedge clk); #2; cycles++;
        end
        check(done===1'b1,"SPI bounded completion");
        check(rx_data===returned,"SPI received independent target response");
        check(sck===expected_pol && cs_n===1'b1,"SPI final clock and CS state");
        monitor_active=0; transfers++; mode_bytes[mode][value]=1;
        @(negedge clk); cpol=expected_pol; cpha=expected_phase; half_period=divider;
    endtask

    task automatic finish_report;
        integer m;
        $display("RESULT spi transfers=%0d checks=%0d",transfers,checks);
        for(m=0;m<4;m++) $display("COVER spi_mode%0d_bytes %0d 256",m,$countones(mode_bytes[m]));
        $display("COVER spi_mode_divider_cross %0d 12",$countones(mode_dividers));
        $display("VERIFICATION_PASS spi"); $finish;
    endtask

    integer m,d,b,divider;
    initial begin
        smoke=$test$plusargs("SMOKE"); waves=$test$plusargs("WAVES");
        for(m=0;m<4;m++) mode_bytes[m]=0;
        if($value$plusargs("VCD=%s",vcd_path)) begin $dumpfile(vcd_path); $dumpvars(0,tb_spi); end
        reset_dut();
        if(waves) begin
            for(m=0;m<4;m++) transfer(m,4,8'hA6,8'h3C,0);
            finish_report();
        end
        if(smoke) begin transfer(0,4,8'h00,8'h00,0); finish_report(); end
        for(m=0;m<4;m++) begin
            for(d=0;d<3;d++) begin
                case(d) 0: divider=2; 1: divider=3; default: divider=7; endcase
                for(b=0;b<256;b++) transfer(m,divider,b[7:0],b[7:0]^8'hA7,0);
                mode_dividers[m*3+d]=1;
            end
            transfer(m,3,8'h96,8'h69,1);
        end
        $display("COVER spi_busy_config_latch 4 4");
        // Invalid divisors cannot assert CS or begin a transaction.
        for(d=0;d<2;d++) begin
            @(negedge clk); half_period=d; valid=1;
            @(posedge clk); #2;
            check(config_error===1'b1 && cs_n===1'b1 && busy===1'b0,"SPI invalid divider rejected");
            @(negedge clk); valid=0;
        end
        $display("COVER spi_invalid_divider 2 2");
        // Abort mid-word. The target monitor is disabled for intentional reset.
        @(negedge clk); half_period=4; valid=1;
        repeat(8) @(negedge clk);
        reset_dut();
        repeat(20) @(negedge clk);
        check(!done && !busy && cs_n,"SPI reset abort no ghost completion");
        transfer(3,4,8'hC5,8'h5C,0);
        $display("COVER spi_reset_abort 1 1");
        check(&mode_dividers,"SPI mode-divider bins complete");
        for(m=0;m<4;m++) check(&mode_bytes[m],"SPI mode-byte bins complete");
        finish_report();
    end
    initial begin #20000000; $fatal(1,"ASSERTION global SPI watchdog timeout"); end
endmodule

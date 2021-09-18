from migen import *

from litex.soc.interconnect.csr import *

# ------------------------------------------------------------------
# -- fiftyfivenm_adcblock parameterized megafunction component declaration
# -- Generated with 'mega_defn_creator' loader - do not edit
# ------------------------------------------------------------------
# component fiftyfivenm_adcblock
# 	generic (
# 		analog_input_pin_mask	:	natural := 0;
# 		clkdiv	:	natural := 1;
# 		device_partname_fivechar_prefix	:	string := "none";
# 		enable_usr_sim	:	natural := 0;
# 		is_this_first_or_second_adc	:	natural := 1;
# 		lpm_hint	:	string := "UNUSED";
# 		lpm_type	:	string := "fiftyfivenm_adcblock";
# 		prescalar	:	natural := 0;
# 		pwd	:	natural := 0;
# 		reference_voltage_sim	:	natural := 65536;
# 		refsel	:	natural := 0;
# 		reserve_block	:	string := "false";
# 		simfilename_ch0	:	string := "simfilename_ch0";
# 		simfilename_ch1	:	string := "simfilename_ch1";
# 		simfilename_ch10	:	string := "simfilename_ch10";
# 		simfilename_ch11	:	string := "simfilename_ch11";
# 		simfilename_ch12	:	string := "simfilename_ch12";
# 		simfilename_ch13	:	string := "simfilename_ch13";
# 		simfilename_ch14	:	string := "simfilename_ch14";
# 		simfilename_ch15	:	string := "simfilename_ch15";
# 		simfilename_ch16	:	string := "simfilename_ch16";
# 		simfilename_ch2	:	string := "simfilename_ch2";
# 		simfilename_ch3	:	string := "simfilename_ch3";
# 		simfilename_ch4	:	string := "simfilename_ch4";
# 		simfilename_ch5	:	string := "simfilename_ch5";
# 		simfilename_ch6	:	string := "simfilename_ch6";
# 		simfilename_ch7	:	string := "simfilename_ch7";
# 		simfilename_ch8	:	string := "simfilename_ch8";
# 		simfilename_ch9	:	string := "simfilename_ch9";
# 		testbits	:	natural := 66;
# 		tsclkdiv	:	natural := 1;
# 		tsclksel	:	natural := 0	);
# 	port(
# 		chsel	:	in std_logic_vector(4 downto 0) := (others => '0');
# 		clk_dft	:	out std_logic;
# 		clkin_from_pll_c0	:	in std_logic := '0';
# 		dout	:	out std_logic_vector(11 downto 0);
# 		eoc	:	out std_logic;
# 		soc	:	in std_logic := '0';
# 		tsen	:	in std_logic := '0';
# 		usr_pwd	:	in std_logic := '0'
# 	);
# end component;

class Max10ADC(Module, AutoCSR):
    def __init__(self, adc_num: int):
        self.adc_num = adc_num
        self.chsel = CSRStorage(5)
        self.result = CSRStatus(12)
        self.clk_dft = Signal()
        self.soc = CSRStorage()
        self.eoc = CSRStatus()
        self.tsen = CSRStorage()
        self.user_pwd = CSRStorage()

        self.adc_clk_cnt = Signal(8)
        self.sync.adc += self.adc_clk_cnt.eq(self.adc_clk_cnt + 1)

        self.specials += Instance("fiftyfivenm_adcblock",
            name = f"adcblock{adc_num}",
            i_chsel = self.chsel.storage,
            i_soc = self.soc.storage,
            i_clkin_from_pll_c0 = ClockSignal("adc"),
            i_tsen = self.tsen.storage,
            i_usr_pwd = self.user_pwd.storage,
            o_dout = self.result.status,
            o_clk_dft = self.clk_dft,
            o_eoc = self.eoc.status,
        )

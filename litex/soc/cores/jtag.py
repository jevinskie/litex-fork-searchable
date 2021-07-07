#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2017 Robert Jordens <jordens@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer

from litex.soc.interconnect import stream

# JTAG TAP FSM -------------------------------------------------------------------------------------

class JTAGTAPFSM(Module):
    def __init__(self, tms: Signal, jtag_clk: Signal, jtag_rst: Signal):
        self.clock_domains.cd_jtag = cd_jtag = ClockDomain("jtag")
        self.comb += [
            ClockSignal('jtag').eq(jtag_clk),
            ResetSignal('jtag').eq(jtag_rst),
        ]

        self.submodules.fsm = fsm = FSM(clock_domain=cd_jtag.name)

        self.tck_cnt = tck_cnt = Signal(16)
        self.sync.jtag += tck_cnt.eq(tck_cnt + 1)

        self.test_logic_reset = tlr = Signal()
        fsm.act('test_logic_reset',
            tlr.eq(1),
            If(~tms, NextState('run_test_idle'))
        )
        self.run_test_idle = rti = Signal()
        fsm.act('run_test_idle',
            rti.eq(1),
            If(tms, NextState('select_dr_scan'))
        )

        # DR
        self.select_dr_scan = sds = Signal()
        fsm.act('select_dr_scan',
            sds.eq(1),
            If(~tms, NextState('capture_dr')).Else(NextState('select_ir_scan'))
        )
        self.capture_dr = cd = Signal()
        fsm.act('capture_dr',
            cd.eq(1),
            If(~tms, NextState('shift_dr')).Else(NextState('exit1_dr'))
        )
        self.shift_dr = sd = Signal()
        fsm.act('shift_dr',
            sd.eq(1),
            If(tms, NextState('exit1_dr'))
        )
        self.exit1_dr = e1d = Signal()
        fsm.act('exit1_dr',
            e1d.eq(1),
            If(~tms, NextState('pause_dr')).Else(NextState('update_dr'))
        )
        self.pause_dr = pd = Signal()
        fsm.act('pause_dr',
            pd.eq(1),
            If(tms, NextState('exit2_dr'))
        )
        self.exit2_dr = e2d = Signal()
        fsm.act('exit2_dr',
            e2d.eq(1),
            If(tms, NextState('update_dr')).Else(NextState('shift_dr'))
        )
        self.update_dr = ud = Signal()
        fsm.act('update_dr',
            ud.eq(1),
            If(tms, NextState('select_dr_scan')).Else(NextState('run_test_idle'))
        )

        # IR
        self.select_ir_scan = sis = Signal()
        fsm.act('select_ir_scan',
            sis.eq(1),
            If(~tms, NextState('capture_ir')).Else(NextState('test_logic_reset'))
        )
        self.capture_ir = ci = Signal()
        fsm.act('capture_ir',
            ci.eq(1),
            If(~tms, NextState('shift_ir')).Else(NextState('exit1_ir'))
        )
        self.shift_ir = si = Signal()
        fsm.act('shift_ir',
            si.eq(1),
            If(tms, NextState('exit1_ir'))
        )
        self.exit1_ir = e1i = Signal()
        fsm.act('exit1_ir',
            e1i.eq(1),
            If(~tms, NextState('pause_ir')).Else(NextState('update_ir'))
        )
        self.pause_ir = pi = Signal()
        fsm.act('pause_ir',
            pi.eq(1),
            If(tms, NextState('exit2_ir'))
        )
        self.exit2_ir = e2i = Signal()
        fsm.act('exit2_ir',
            e2i.eq(1),
            If(tms, NextState('update_ir')).Else(NextState('shift_ir'))
        )
        self.update_ir = ui = Signal()
        fsm.act('update_ir',
            ui.eq(1),
            If(tms, NextState('select_dr_scan')).Else(NextState('run_test_idle'))
        )

# Altera VJTAG -------------------------------------------------------------------------------------

class AlteraVJTAG(Module):
    def __init__(self, chain=1):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()
        #
        self.runtest = Signal()

        self.tck = Signal()
        self.tms = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        # # #

        self.specials += Instance("sld_virtual_jtag",
            p_sld_auto_instance_index = "NO",
            p_sld_instance_index = chain - 1,
            # p_sld_ir_width = 1,
            # p_sld_sim_n_scan = 0,
            # p_sld_sim_action = "UNUSED",
            # p_sld_sim_total_length = 0,

            o_jtag_state_tlr    = self.reset,
            o_virutal_state_cdr = self.capture,
            o_virtual_state_sdr = self.shift,
            o_virtual_state_udr = self.update,
            #
            o_jtag_state_rti    = self.runtest,

            o_tck = self.tck,
            o_tms = self.tms,
            o_tdi = self.tdi,
            i_tdo = self.tdo,
        )

class AlteraJTAG(Module):
    def __init__(self, primitive: str, reserved_pads: Record, chain=1):
        self.reset   = reset   = Signal() # FIXME
        self.capture = capture = Signal() # FIXME
        self.shift   = shift   = Signal()
        self.update  = update  = Signal()
        #
        self.runtest = runtest = Signal()
        self.drck    = drck    = Signal()
        self.sel     = sel     = Signal()

        # self.tck = tck = Signal()
        # self.tms = tms = Signal()
        # self.tdi = tdi = Signal()
        # self.tdo = tdo = Signal()

        self.altera_reserved_tck = rtck = Signal()
        self.altera_reserved_tms = rtms = Signal()
        self.altera_reserved_tdi = rtdi = Signal()
        self.altera_reserved_tdo = rtdo = Signal()

        # inputs
        # self.tdoutap = tdoutap = Signal() # fails synth on max10
        self.tdouser = tdouser = Signal()
        self.tmscore = tmscore = Signal()
        self.tckcore = tckcore = Signal()
        self.tdicore = tdicore = Signal()
        # self.corectl = corectl = Signal()
        # self.ntdopinena = ntdopinena = Signal()

        # outputs
        self.tmsutap = tmsutap = Signal()
        self.tckutap = tckutap = Signal()
        self.tdiutap = tdiutap = Signal()
        self.tdocore = tdocore = Signal()

        assert 1 <= chain <= 1

        # # #

        self.specials += Instance(primitive,
            # o_???          = reset,
            # o_???          = capture,
            o_shiftuser      = shift,
            o_updateuser     = update,
            #
            o_runidleuser    = runtest,
            o_clkdruser      = drck,
            o_usr1user       = sel,


            # etc?
            # i_tdoutap = tdoutap, # fails synth on max20
            i_tdouser = tdouser,
            i_tmscore = tmscore,
            i_tckcore = tckcore,
            i_tdicore = tdicore,
            # i_corectl = corectl,
            # i_ntdopinena = ntdopinena,

            o_tmsutap = tmsutap,
            o_tckutap = tckutap,
            o_tdiutap = tdiutap,
            o_tdocore = tdocore,

            # reserved pins
            i_tms = rtms,
            i_tck = rtck,
            i_tdi = rtdi,
            o_tdo = rtdo,
        )

        self.comb += [
            rtms.eq(reserved_pads.altera_reserved_tms),
            rtck.eq(reserved_pads.altera_reserved_tck),
            rtdi.eq(reserved_pads.altera_reserved_tdi),
            reserved_pads.altera_reserved_tdo.eq(rtdo),
        ]

        # self.comb += [
            # tck.eq(tckcore),
            # tms.eq(tmscore),
            # tdi.eq(tdicore),
            # tdocore.eq(tdo),
        # ]



class MAX10JTAG(AlteraJTAG):
    def __init__(self, reserved_pads: Record, *args, **kwargs):
        AlteraJTAG.__init__(self, "fiftyfivenm_jtag", reserved_pads, *args, **kwargs)

# Altera Atlantic JTAG (UART over JTAG) ------------------------------------------------------------

class JTAGAtlantic(Module):
    def __init__(self):
        self.sink   =   sink = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8)])

        # # #

        self.specials += Instance("alt_jtag_atlantic",
            # Parameters
            p_LOG2_RXFIFO_DEPTH       = "5", # FIXME: expose?
            p_LOG2_TXFIFO_DEPTH       = "5", # FIXME: expose?
            p_SLD_AUTO_INSTANCE_INDEX = "YES",

            # Clk/Rst
            i_clk   = ClockSignal("sys"),
            i_rst_n = ~ResetSignal("sys"),

            # TX
            i_r_dat = sink.data,
            i_r_val = sink.valid,
            o_r_ena = sink.ready,

            # RX
            o_t_dat = source.data,
            i_t_dav = source.ready,
            o_t_ena = source.valid,
        )

# Xilinx JTAG --------------------------------------------------------------------------------------

class XilinxJTAG(Module):
    def __init__(self, primitive, chain=1):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()
        #
        self.runtest = Signal()
        self.drck    = Signal()
        self.sel     = Signal()

        self.tck = Signal()
        self.tms = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        assert 1 <= chain <= 4

        # # #

        self.specials += Instance(primitive,
            p_JTAG_CHAIN = chain,

            o_RESET   = self.reset,
            o_CAPTURE = self.capture,
            o_SHIFT   = self.shift,
            o_UPDATE  = self.update,
            #
            o_RUNTEST = self.runtest,
            o_DRCK    = self.drck,
            o_SEL     = self.sel,

            o_TCK = self.tck,
            o_TMS = self.tms,
            o_TDI = self.tdi,
            i_TDO = self.tdo,
        )

class S6JTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCAN_SPARTAN6", *args, **kwargs)


class S7JTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCANE2", *args, **kwargs)


class USJTAG(XilinxJTAG):
    def __init__(self, *args, **kwargs):
        XilinxJTAG.__init__(self, primitive="BSCANE2", *args, **kwargs)

# JTAG PHY -----------------------------------------------------------------------------------------

class JTAGPHY(Module):
    def __init__(self, jtag=None, device=None, data_width=8, clock_domain="sys", chain=1):
        """JTAG PHY

        Provides a simple JTAG to LiteX stream module to easily stream data to/from the FPGA
        over JTAG.

        Wire format: data_width + 2 bits, LSB first.

        Host to Target:
          - TX ready : bit 0
          - RX data: : bit 1 to data_width
          - RX valid : bit data_width + 1

        Target to Host:
          - RX ready : bit 0
          - TX data  : bit 1 to data_width
          - TX valid : bit data_width + 1
        """
        self.sink   =   sink = stream.Endpoint([("data", data_width)])
        self.source = source = stream.Endpoint([("data", data_width)])

        # # #

        valid = Signal()
        data  = Signal(data_width)
        count = Signal(max=data_width)

        # JTAG TAP ---------------------------------------------------------------------------------
        if jtag is None:
            if device[:3] == "xc6":
                jtag = S6JTAG(chain=chain)
            elif device[:3] == "xc7":
                jtag = S7JTAG(chain=chain)
            elif device[:4] in ["xcku", "xcvu"]:
                jtag = USJTAG(chain=chain)
            elif device[:3].lower() in ["10m"]:
                jtag = AlteraJTAG(chain=chain)
            else:
                raise NotImplementedError
            self.submodules.jtag = jtag

        # JTAG clock domain ------------------------------------------------------------------------
        self.clock_domains.cd_jtag = ClockDomain()
        self.comb += ClockSignal("jtag").eq(jtag.tck)
        self.specials += AsyncResetSynchronizer(self.cd_jtag, ResetSignal(clock_domain))

        # JTAG clock domain crossing ---------------------------------------------------------------
        if clock_domain != "jtag":
            tx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            tx_cdc = ClockDomainsRenamer({"write": clock_domain, "read": "jtag"})(tx_cdc)
            rx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            rx_cdc = ClockDomainsRenamer({"write": "jtag", "read": clock_domain})(rx_cdc)
            self.submodules.tx_cdc = tx_cdc
            self.submodules.rx_cdc = rx_cdc
            self.comb += [
                sink.connect(tx_cdc.sink),
                rx_cdc.source.connect(source)
            ]
            sink, source = tx_cdc.source, rx_cdc.sink

        # JTAG Xfer FSM ----------------------------------------------------------------------------
        fsm = FSM(reset_state="XFER-READY")
        fsm = ClockDomainsRenamer("jtag")(fsm)
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(jtag.reset | jtag.capture)
        fsm.act("XFER-READY",
            jtag.tdo.eq(source.ready),
            If(jtag.shift,
                sink.ready.eq(jtag.tdi),
                NextValue(valid, sink.valid),
                NextValue(data,  sink.data),
                NextValue(count, 0),
                NextState("XFER-DATA")
            )
        )
        fsm.act("XFER-DATA",
            jtag.tdo.eq(data),
            If(jtag.shift,
                NextValue(count, count + 1),
                NextValue(data, Cat(data[1:], jtag.tdi)),
                If(count == (data_width - 1),
                    NextState("XFER-VALID")
                )
            )
        )
        fsm.act("XFER-VALID",
            jtag.tdo.eq(valid),
            If(jtag.shift,
                source.valid.eq(jtag.tdi),
                NextState("XFER-READY")
            )
        )
        self.comb += source.data.eq(data)

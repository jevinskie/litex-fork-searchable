from migen import *


class MonitorArg:
    def __init__(self, signal, name=None, fmt=None, on_change=True):
        self.signal = signal
        self.name = name
        self.fmt = fmt
        self.on_change = on_change


class Monitor(Module):
    """
    Monitor("tx_data: %0b rx_data: %0b", tx_data, rx_data)

    Monitor("tick: %0d tx_data: {txd} rx_data: %0b",
        MonitorArg(nclks, on_change=False),
        MonitorArg(tx_data, "txd", "%0b"),
        rx_data,
    )
    """

    def __init__(self, fmt, *args):
        arg_sigs = []
        monitored_sigs = []
        fmt_replacements = {}
        for arg in args:
            if isinstance(arg, MonitorArg):
                arg_sigs.append(arg.signal)
                if arg.fmt is not None:
                    fmt_replacements[arg.name] = arg.fmt
                if arg.on_change:
                    monitored_sigs.append(arg.signal)
            else:
                arg_sigs.append(arg)
                monitored_sigs.append(arg)
        fmt = fmt.format(**fmt_replacements)

        old_vals = {sig: Signal.like(sig) for sig in monitored_sigs}
        changed = Signal()

        for sig, old_sig in old_vals.items():
            self.sync += old_sig.eq(sig)
            self.comb += changed.eq(changed | (old_sig != sig))

        self.sync += If(changed, Display(fmt, *arg_sigs))

from typing import Union

from migen import *
from litex.soc.cores.clock.common import ClockFrequency

class MultiWaitTimer(Module):
    class Ticks(int): ...
    class Seconds(float): ...

    def __init__(
            self,
            durations: dict[str, Union[Ticks, Seconds]],
            cd="sys"):
        dur_ticks = {}

        self.wait = Signal()

        for name, dur in durations.items():
            if isinstance(dur, MultiWaitTimer.Seconds):
                dur_ticks[name] = dur * ClockFrequency(cd)
            else:
                dur_ticks[name] = dur
        max_ticks = max(dur_ticks.values())
        deadlines = {n: max_ticks - t for n, t in dur_ticks.items()}

        for name in deadlines.keys():
            setattr(self, f"{name}_done", Signal(name=f"{name}_done"))

        # # #

        done_overall = Signal()
        count = Signal(bits_for(max_ticks), reset=max_ticks)
        self.comb += done_overall.eq(count == 0)
        self.sync += \
            If(self.wait,
                If(~done_overall, count.eq(count - 1))
            ).Else(count.eq(count.reset))

        for name, deadline in deadlines.items():
            self.sync += \
                If(self.wait,
                    If(count == deadline,
                        getattr(self, f"{name}_done").eq(1)
                    )
                ).Else(getattr(self, f"{name}_done").eq(0))

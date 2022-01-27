from collections import OrderedDict

from migen.fhdl.module import Module
from migen.fhdl.structure import Signal

import wrapt

def _signals(self, recurse=False):
    signals = set()
    for attr_name in dir(self):
        if attr_name == "_signals" or attr_name == "_signals_r" or attr_name == "_get_signals" \
                or (attr_name[:2] == "__" and attr_name[-2:] == "__"):
            # break infinite recursion
            continue
        attr = getattr(self, attr_name)
        if isinstance(attr, Signal):
            signals.add(attr)
    if recurse:
        if hasattr(self, "_submodules"):
            for submod_name, submod in self._submodules:
                signals |= submod._signals(recurse=True)
    return set(signals)

Module._signals = _signals

@wrapt.patch_function_wrapper("migen.genlib.fsm", "FSM.__init__")
def FSM_init_patched(__init__, self, args, kwargs):
    __init__(*args, **kwargs)
    self.ongoing_signals = OrderedDict()

@wrapt.patch_function_wrapper("migen.genlib.fsm", "FSM.ongoing")
def FSM_ongoing_patched(ongoing, self, args, kwargs):
    state = args[0]
    # fix FSM ongoing reset states
    is_ongoing = ongoing(*args, **kwargs)
    is_ongoing.reset = 1 if state == self.reset_state else 0
    self.ongoing_signals[state] = is_ongoing
    return is_ongoing

@wrapt.patch_function_wrapper("migen.genlib.fsm", "FSM.do_finalize")
def FSM_do_finalize_patched(do_finalize, self, args, kwargs):
    for state, is_ongoing in self.ongoing_signals.items():
        if is_ongoing.reset.value:
            # since the default is high, explicitly deassert in all other states
            for other_state in set(self.actions) - set([state]):
                self.actions[other_state].append(is_ongoing.eq(0))
    do_finalize(*args, *kwargs)

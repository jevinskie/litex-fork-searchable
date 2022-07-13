CORE_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
include $(CORE_DIR)/Makefile.common

SRCS_SIM_CPP = sim_init.cpp $(SRC_DIR)/veril.cpp

CC_SRCS ?= "--cc sim.v"

all: modules sim

$(OBJS_SIM): %.o: $(SRC_DIR)/%.c | mkdir
	$(CC) -c $(CFLAGS) -o $(OBJ_DIR)/$@ $<

.PHONY: sim
sim: $(OBJS_SIM) | mkdir
	verilator -Wno-fatal -O3 $(CC_SRCS) --exe \
		-DPRINTF_COND=0 \
		$(SRCS_SIM_CPP) $(OBJS_SIM) \
		--top-module sim \
		$(if $(THREADS), --threads $(THREADS),) \
		-CFLAGS "$(CFLAGS) -Wno-tautological-compare -I$(SRC_DIR)" \
		-LDFLAGS "$(LDFLAGS)" \
		--trace \
		$(if $(TRACE_FST), --trace-fst,) \
		$(if $(COVERAGE), --coverage,) \
		--unroll-count 256 \
		--output-split 5000 \
		--output-split-cfuncs 500 \
		--output-split-ctrace 500 \
		$(INC_DIR) \
		-Wno-BLKANDNBLK \
		-Wno-WIDTH \
		-Wno-COMBDLY \
		-Wno-CASEINCOMPLETE
	make -j -C $(OBJ_DIR) -f Vsim.mk Vsim

.PHONY: clean
clean:
	rm -rf modules $(OBJ_DIR)

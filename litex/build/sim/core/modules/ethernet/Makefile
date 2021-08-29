include ../../variables.mak
UNAME_S := $(shell uname -s)

include $(SRC_DIR)/modules/rules.mak

CFLAGS += -I/usr/local/opt/tapcfg/include -I/opt/homebrew/opt/tapcfg/include -I/opt/brew/opt/tapcfg/include
LDFLAGS += -L/usr/local/opt/tapcfg/lib -L/opt/homebrew/opt/tapcfg/lib -L/opt/brew/opt/tapcfg/lib -ltapcfg
# OBJS = $(MOD).o tapcfg.o taplog.o
OBJS = $(MOD).o

$(MOD).so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^ -lpcap
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^ -lpcap
endif

# tapcfg.o: $(TAPCFG_DIRECTORY)/src/lib/tapcfg.c
# 	$(CC) $(CFLAGS) -c -o $@ $<

# taplog.o: $(TAPCFG_DIRECTORY)/src/lib/taplog.c
# 	$(CC) $(CFLAGS) -c -o $@ $<

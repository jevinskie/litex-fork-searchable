include ../../variables.mak
UNAME_S := $(shell uname -s)

include $(SRC_DIR)/modules/rules.mak

CFLAGS += -I/usr/local/opt/tapcfg/include -I/opt/homebrew/opt/tapcfg/include -I/opt/brew/opt/tapcfg/include -I$(HOME)/base/tapcfg/include -Wno-error
LDFLAGS += -L/usr/local/opt/tapcfg/lib -L/opt/homebrew/opt/tapcfg/lib -L/opt/brew/opt/tapcfg/lib -L$(HOME)/base/tapcfg/lib
# OBJS = $(MOD).o tapcfg.o taplog.o
OBJS = $(MOD).o

$(MOD).so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^ -lpcap -ltapcfg
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^ -lpcap -ltapcfg
endif

# tapcfg.o: $(TAPCFG_DIRECTORY)/src/lib/tapcfg.c
# 	$(CC) $(CFLAGS) -c -o $@ $<

# taplog.o: $(TAPCFG_DIRECTORY)/src/lib/taplog.c
# 	$(CC) $(CFLAGS) -c -o $@ $<

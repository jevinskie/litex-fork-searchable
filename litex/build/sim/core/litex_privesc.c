#include <error.h>
#include <errno.h>
#include <libgen.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>

#include <cap-ng.h>

void add_ambcap(int ambcap) {
	int res = -1;

	capng_get_caps_process();
	res = capng_update(CAPNG_ADD, CAPNG_INHERITABLE, ambcap);
	if (res) {
		error(1, res, "couldn't add ambcap %d to inheritable set", ambcap);
	}
	capng_apply(CAPNG_SELECT_CAPS);
	res = prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, ambcap, 0, 0);
	if (res) {
		error(2, res, "coudln't add ambcap %d to ambient set", ambcap);
	}
}

int main(int argc,  char * const *argv) {
	int res = -1;

	if (argc < 2) {
		error(3, ENOENT, "must provide a binary, e.g. %s <full path to run binary>", dirname(strdup(argv[0])));
	}

	add_ambcap(CAP_NET_ADMIN);
	add_ambcap(CAP_NET_RAW);

	res = execv(argv[1], &argv[1]);
	if (res) {
		error(4, errno, "bad execv of %s", argv[1]);
	}

	return 0;
}

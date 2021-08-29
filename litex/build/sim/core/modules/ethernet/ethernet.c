#include <assert.h>
#include <arpa/inet.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <limits.h>
#include "error.h"

#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>
#include <json-c/json.h>
#include <pcap/pcap.h>
#include <tapcfg.h>
#include "modules.h"

#ifdef __APPLE__
#define GW
#endif

#ifdef GW
#include <net/if.h>
#include <sys/ioctl.h>
#endif

#define PCAP_FILENAME "./sim.pcap"

static const char macadr[6] = {0xaa, 0xb6, 0x24, 0x69, 0x77, 0x21};
static unsigned char ipadr[4] = {0};
#ifdef GW
static unsigned char gwipadr[4] = {0};
#endif

struct eth_packet_s {
  char data[2000];
  size_t len;
  struct eth_packet_s *next;
};

struct session_s {
  char *tx;
  char *tx_valid;
  char *tx_ready;
  char *rx;
  char *rx_valid;
  char *rx_ready;
  char *sys_clk;
  tapcfg_t *tapcfg;
  int fd;
  char databuf[2000];
  int datalen;
  char inbuf[2000];
  int inlen;
  int insent;
  struct eth_packet_s *ethpack;
  struct event *ev;
  pcap_t *pcap;
  pcap_dumper_t *pcap_dumper;
};

static struct event_base *base=NULL;

int litex_sim_module_get_args(char *args, char *arg, char **val)
{
  int ret = RC_OK;
  json_object *jsobj = NULL;
  json_object *obj = NULL;
  char *value = NULL;
  int r;

  jsobj = json_tokener_parse(args);
  if(NULL == jsobj) {
    fprintf(stderr, "Error parsing json arg: %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }

  if(!json_object_is_type(jsobj, json_type_object)) {
    fprintf(stderr, "Arg must be type object! : %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }

  obj=NULL;
  r = json_object_object_get_ex(jsobj, arg, &obj);
  if(!r) {
    fprintf(stderr, "Could not find object: \"%s\" (%s)\n", arg, args);
    ret = RC_JSERROR;
    goto out;
  }
  value = strdup(json_object_get_string(obj));

out:
  *val = value;
  return ret;
}

static int litex_sim_module_pads_get(struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
  void *sig = NULL;
  int i;

  if(!pads || !name || !signal) {
    ret=RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name)) {
      sig=(void*)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal=sig;
  return ret;
}

static int ethernet_start(void *b)
{
  base = (struct event_base *) b;
  printf("[ethernet] loaded (%p)\n", base);
  return RC_OK;
}

void event_handler(int fd, short event, void *arg)
{
  struct session_s *s = (struct session_s*)arg;
  struct eth_packet_s *ep;
  struct eth_packet_s *tep;
  char buf[2000];
  int len = -1;

  if (event & EV_READ) {
    ep = malloc(sizeof(struct eth_packet_s));
    memset(ep, 0, sizeof(struct eth_packet_s));
    ep->len = tapcfg_read(s->tapcfg, ep->data, 2000);
    // fprintf(stderr, "eth read %d\n", (int)ep->len);
    assert(ep->len >= 0);
    if(ep->len < 60)
      ep->len = 60;

    if(!s->ethpack)
      s->ethpack = ep;
    else {
      for(tep=s->ethpack; tep->next; tep=tep->next);
      tep->next = ep;
    }
  }
#ifdef __APPLE__
  else if (event & EV_TIMEOUT) {
    do {
      len = tapcfg_read(s->tapcfg, buf, sizeof(buf));
      if (len >= 0) {
        // fprintf(stderr, "eth read BLIND %d\n", len);
        ep = malloc(sizeof(struct eth_packet_s));
        memset(ep, 0, sizeof(struct eth_packet_s));
        ep->len = len;
        memcpy(ep->data, buf, len);
        if(ep->len < 60)
          ep->len = 60;

        if(!s->ethpack)
          s->ethpack = ep;
        else {
          for(tep=s->ethpack; tep->next; tep=tep->next);
          tep->next = ep;
        }
      }
    } while (len >= 0);
  }
#endif
}


static int ethernet_new(void **sess, char *args)
{
  int ret = RC_OK;
  char *c_tap = NULL;
  char *c_tap_ip = NULL;
  char *ifname = NULL;
  struct session_s *s = NULL;
#ifndef __APPLE__
  struct timeval tv_tap_read_timeout = {10, 0};
#else
  // Mac TUN/TAP driver doesn't support kqueue - must use short timeouts to get read events
  struct timeval tv_tap_read_timeout = {0, 10000}; // 1000 seems to break SIGINT
#endif

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }

  s=(struct session_s*)malloc(sizeof(struct session_s));
  if(!s) {
    ret=RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

  ret = litex_sim_module_get_args(args, "interface", &c_tap);
  {
    if(RC_OK != ret)
      goto out;
  }
  ret = litex_sim_module_get_args(args, "ip", &c_tap_ip);
  {
    if(RC_OK != ret)
      goto out;
  }

  struct in_addr ia, ia_gw;
  int inet_aton_res = inet_aton(c_tap_ip, &ia);
  assert(inet_aton_res == 1);
  memcpy(ipadr, &ia.s_addr, sizeof(ipadr));
#ifdef GW
  char c_gw_ip[16] = {0};
  snprintf(c_gw_ip, sizeof(c_gw_ip), "%d.%d.%d.1", ipadr[0], ipadr[1], ipadr[2]);
  inet_aton_res = inet_aton(c_gw_ip, &ia_gw);
  assert(inet_aton_res == 1);
  memcpy(gwipadr, &ia_gw.s_addr, sizeof(gwipadr));
#endif

  s->tapcfg = tapcfg_init();
  tapcfg_start(s->tapcfg, c_tap, 0);

#ifdef __linux__
  char sysctl_path[PATH_MAX] = {0};
  snprintf(sysctl_path, sizeof(sysctl_path), "/proc/sys/net/ipv6/conf/%s/disable_ipv6", c_tap);
  int sysctl_fd = open(sysctl_path, O_WRONLY);
  assert(sysctl_fd >= 0);
  ssize_t sysctl_write_res = write(sysctl_fd, "1", 1);
  assert(sysctl_write_res == 1);
  assert(!close(sysctl_fd));
#endif

  ifname = tapcfg_get_ifname(s->tapcfg);
  s->fd = tapcfg_get_fd(s->tapcfg);
#ifdef __APPLE__
  // don't block during speculative, timer callback reads
  fcntl(s->fd, F_SETFL, fcntl(s->fd, F_GETFL, 0) | O_NONBLOCK);
#endif
  tapcfg_iface_set_hwaddr(s->tapcfg, macadr, 6);
#ifndef GW
  tapcfg_iface_set_ipv4(s->tapcfg, c_tap_ip, 24);
#else
  tapcfg_iface_set_ipv4(s->tapcfg, c_gw_ip, 24);
  tapcfg_iface_add_ipv4(s->tapcfg, c_tap_ip, 32);  // TODO: Why 32?
  char route_cmd_buf[256] = {0};
  snprintf(route_cmd_buf, sizeof(route_cmd_buf),
    "route add %d.%d.%d.%d -ifp tap%d %d.%d.%d.%d",
    ipadr[0], ipadr[1], ipadr[2], ipadr[3],
    atoi(&ifname[3]),
    gwipadr[0], gwipadr[1], gwipadr[2], gwipadr[3]
  );
  fprintf(stderr, "running '%s'\n", route_cmd_buf);
  ret = system(route_cmd_buf);
  assert(!ret);
#endif
  free(c_tap_ip);

  s->ev = event_new(base, s->fd, EV_READ | EV_PERSIST, event_handler, s);
  event_add(s->ev, &tv_tap_read_timeout);

  char pcap_errbuf[PCAP_ERRBUF_SIZE];
  // int pcap_init_res = pcap_init(PCAP_CHAR_ENC_UTF_8, pcap_errbuf);
  // if (pcap_init_res) {
  //   fprintf(stderr, "pcap_init error: %s\n", pcap_errbuf);
  //   goto out;
  // }
  fprintf(stderr, "pcappin' %s\n", c_tap);
  s->pcap = pcap_create(c_tap, pcap_errbuf);
  free(c_tap);
  if (!s->pcap) {
    fprintf(stderr, "pcap_create error: %s\n", pcap_errbuf);
    // goto out;
    assert(0);
  }
  int pcap_set_promisc_res = pcap_set_promisc(s->pcap, 1);
  if (pcap_set_promisc_res) {
    fprintf(stderr, "couldn't set promisc mode\n");
    // goto out;
    assert(0);
  }
  int pcap_setres_res = pcap_set_tstamp_precision(s->pcap, PCAP_TSTAMP_PRECISION_NANO);
  if (pcap_setres_res) {
    fprintf(stderr, "couldn't set pcap precision to nanoseconds\n");
    // goto out;
#ifndef __APPLE__
    assert(0);
#endif
  }
  int pcap_set_timeout_res = pcap_set_timeout(s->pcap, 1);
  if (pcap_set_timeout_res) {
    fprintf(stderr, "couldn't set pcap timeout to 1 ms\n");
    // goto out;
    assert(0);
  }
  int pcap_set_nonblock_res = pcap_setnonblock(s->pcap, 1, pcap_errbuf);
  if (pcap_set_nonblock_res) {
    fprintf(stderr, "couldn't set pcap to nonblocking: %s\n", pcap_errbuf);
    // goto out;
    assert(0);
  }
  int pcap_activate_res = pcap_activate(s->pcap);
  if (pcap_activate_res) {
    fprintf(stderr, "pcap_activate failed: %d\n", pcap_activate_res);
    // goto out;
    assert(0);
  }
  s->pcap_dumper = pcap_dump_open(s->pcap, PCAP_FILENAME);
  if (!s->pcap_dumper) {
    fprintf(stderr, "pcap_dump_open failed error: %s\n", pcap_geterr(s->pcap));
    // goto out;
    assert(0);
  }

  tapcfg_iface_set_status(s->tapcfg, TAPCFG_STATUS_ALL_UP);

out:
  *sess=(void*)s;
  return ret;
}

static int ethernet_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*)sess;
  struct pad_s *pads;
  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  if(!strcmp(plist->name, "eth")) {
    litex_sim_module_pads_get(pads, "sink_data", (void**)&s->rx);
    litex_sim_module_pads_get(pads, "sink_valid", (void**)&s->rx_valid);
    litex_sim_module_pads_get(pads, "sink_ready", (void**)&s->rx_ready);
    litex_sim_module_pads_get(pads, "source_data", (void**)&s->tx);
    litex_sim_module_pads_get(pads, "source_valid", (void**)&s->tx_valid);
    litex_sim_module_pads_get(pads, "source_ready", (void**)&s->tx_ready);
  }
  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);

out:
  return ret;
}

static int ethernet_tick(void *sess, uint64_t time_ps)
{
  static struct clk_edge_t edge;
  char c;
  struct session_s *s = (struct session_s*)sess;
  struct eth_packet_s *pep;

  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  *s->tx_ready = 1;
  if(*s->tx_valid == 1) {
    c = *s->tx;
    s->databuf[s->datalen++]=c;
  } else {
    if(s->datalen) {
      // fprintf(stderr, "eth write %d\n", (int)s->datalen);
      tapcfg_write(s->tapcfg, s->databuf, s->datalen);
      if (s->pcap) {
        pcap_dispatch(s->pcap, 0, pcap_dump, (u_char *)s->pcap_dumper);
      }
      s->datalen=0;
    }
  }

  *s->rx_valid=0;
  if(s->inlen) {
    *s->rx_valid=1;
    *s->rx = s->inbuf[s->insent++];
    if(s->insent == s->inlen) {
      s->insent =0;
      s->inlen = 0;
    }
  } else {
    if(s->ethpack) {
      memcpy(s->inbuf, s->ethpack->data, s->ethpack->len);
      s->inlen = s->ethpack->len;
      pep=s->ethpack->next;
      free(s->ethpack);
      s->ethpack=pep;
      if (s->pcap) {
        pcap_dispatch(s->pcap, 0, pcap_dump, (u_char *)s->pcap_dumper);
      }
    }
  }
  return RC_OK;
}

static int ethernet_close(void *sess)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*)sess;
  if (s->pcap) {
    pcap_dump_flush(s->pcap_dumper);
    pcap_dump_close(s->pcap_dumper);
    pcap_close(s->pcap);
  }
  return ret;
}

static struct ext_module_s ext_mod = {
  "ethernet",
  ethernet_start,
  ethernet_new,
  ethernet_add_pads,
  ethernet_close,
  ethernet_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}

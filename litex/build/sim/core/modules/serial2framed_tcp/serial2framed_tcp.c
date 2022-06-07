//
// This file is part of LiteX.
//
// Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
// SPDX-License-Identifier: BSD-2-Clause

#undef NDEBUG
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"
#include <unistd.h>
#include <arpa/inet.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>

#include <json-c/json.h>
#include "modules.h"

#define MAX_PACKET_LEN 2000

#define DEBUG

struct tcp_packet_s {
  char data[MAX_PACKET_LEN];
  ssize_t len;
  struct tcp_packet_s *next;
};

struct session_s {
  char *tx;
  char *tx_valid;
  char *tx_ready;
  char *tx_first;
  char *tx_last;
  char *rx;
  char *rx_valid;
  char *rx_ready;
  char *rx_first;
  char *rx_last;
  char *sys_clk;
  int sock;
  int server;
  struct sockaddr_in peer_addr;
  struct tcp_packet_s *tcppack;
  struct event *ev;
  char databuf[MAX_PACKET_LEN];
  int datalen;
  char inbuf[MAX_PACKET_LEN];
  int inlen;
  int insent;
};

struct event_base *base;

#ifdef DEBUG
static void hexdump(const char *name, void *buf, size_t len) {
  printf("%s: ", name);
  const uint8_t *p = (const uint8_t *)buf;
  while (len--) {
    printf("%02hhx ", *p++);
  }
  printf("\n");
}
#endif

int litex_sim_module_get_args(char *args, char *arg, char **val, bool optional)
{
  int ret = RC_OK;
  json_object *jsobj = NULL;
  json_object *obj = NULL;
  char *value = NULL;
  int r;

  if(!arg) {
    eprintf("litex_sim_module_get_args(): `arg` (requested .json key) is NULL!\n");
    ret = RC_JSERROR;
    goto out;
  }

  jsobj = json_tokener_parse(args);
  if(NULL == jsobj) {
    eprintf("Error parsing json arg: %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }
  if(!json_object_is_type(jsobj, json_type_object)) {
    eprintf("Arg must be type object! : %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }
  obj = NULL;
  r = json_object_object_get_ex(jsobj, arg, &obj);
  if(!r) {
    if(!optional) {
      eprintf("Could not find object: \"%s\" (%s)\n", arg, args);
      ret = RC_JSERROR;
    } else {
      ret = RC_JSMISSINGKEY;
    }
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
    ret = RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name)) {
      sig = (void *)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal = sig;
  return ret;
}

static int serial2framed_tcp_start(void *b)
{
  base = (struct event_base *)b;
  printf("[serial2framed_tcp] loaded (%p)\n", base);
  return RC_OK;
}

void read_handler(int fd, short event, void *arg)
{
  struct session_s *s = (struct session_s *)arg;
  struct tcp_packet_s *tp, *ttp;

  tp = malloc(sizeof(struct tcp_packet_s));
  memset(tp, 0, sizeof(struct tcp_packet_s));
  uint32_t pkt_sz;
  int len_field_nbytes = recv(s->sock, &pkt_sz, sizeof(uint32_t), 0);
  if(len_field_nbytes != sizeof(uint32_t)) {
    perror("serial2framed_tcp: recv() of frame length field");
    event_base_loopexit(base, NULL);
    return;
  }
  pkt_sz = ntohl(pkt_sz);
  tp->len = recv(s->sock, &tp->data, pkt_sz, 0);
#ifdef DEBUG
  hexdump("h2d_raw", tp->data, pkt_sz);
#endif
  if(tp->len != pkt_sz) {
    perror("serial2framed_tcp: recv() of frame body");
    event_base_loopexit(base, NULL);
    return;
  }
  assert(tp->len != 0);

  if(!s->tcppack)
    s->tcppack = tp;
  else {
    for(ttp = s->tcppack; tp->next; ttp = ttp->next)
      ;
    ttp->next = tp;
  }
}

static void event_handler(int fd, short event, void *arg)
{
  if(event & EV_READ)
    read_handler(fd, event, arg);
}

static void accept_conn_cb(struct evconnlistener *listener, evutil_socket_t fd, struct sockaddr *address, int socklen, void *ctx)
{
  struct session_s *s = (struct session_s *)ctx;
  struct timeval tv = {1, 0};

  s->sock = fd;
  s->ev = event_new(base, fd, EV_READ | EV_PERSIST, event_handler, s);
  event_add(s->ev, &tv);
}

static void accept_error_cb(struct evconnlistener *listener, void *ctx)
{
  struct event_base *base = evconnlistener_get_base(listener);
  eprintf("ERROR\n");

  event_base_loopexit(base, NULL);
}

static int serial2framed_tcp_new(void **sess, char *args)
{
  int ret = RC_OK;
  struct session_s *s = NULL;
  char *cport = NULL;
  char *cbind_ip = NULL;
  char *sconnect_ip = NULL;
  int port;
  struct evconnlistener *listener;
  struct sockaddr_in sin;
  struct timeval tv_sock_read_timeout = {10, 0};

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }
  ret = litex_sim_module_get_args(args, "port", &cport, false);
  if(RC_OK != ret)
    goto out;

  ret = litex_sim_module_get_args(args, "bind_ip", &cbind_ip, true);
  if(RC_OK != ret) {
    if(RC_JSMISSINGKEY == ret) {
      cbind_ip = "0.0.0.0";
      ret = RC_OK;
    } else {
      goto out;
    }
  }

  ret = litex_sim_module_get_args(args, "connect_ip", &sconnect_ip, true);
  if(RC_OK != ret) {
    if(RC_JSMISSINGKEY == ret) {
      // do nothing, not connecting to a server
      ret = RC_OK;
    } else {
      goto out;
    }
  }

  sscanf(cport, "%d", &port);
  free(cport);
  if(!port) {
    ret = RC_ERROR;
    eprintf("Invalid port selected!\n");
    goto out;
  }

  s = (struct session_s *)malloc(sizeof(struct session_s));
  if(!s) {
    ret = RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));
  if(!sconnect_ip)
    s->server = 1;

  if(s->server) {
    int addr_ret = inet_pton(AF_INET, cbind_ip, &(sin.sin_addr));
    sin.sin_family = AF_INET;
    sin.sin_port = htons(port);
    if(!addr_ret) {
      eprintf("Invalid bind IP ('%s') selected!\n", cbind_ip);
      ret = RC_ERROR;
      goto out;
    }
    listener =
    evconnlistener_new_bind(base, accept_conn_cb, s, LEV_OPT_CLOSE_ON_FREE | LEV_OPT_REUSEABLE, -1, (struct sockaddr *)&sin, sizeof(sin));
    if(!listener) {
      ret = RC_ERROR;
      eprintf("Can't bind port %d\n!\n", port);
      goto out;
    }
    evconnlistener_set_error_cb(listener, accept_error_cb);
  } else {
    s->sock = socket(AF_INET, SOCK_STREAM, 0);
    assert(s->sock >= 0);
    int optval = 1;
    assert(!setsockopt(s->sock, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval)));
    assert(!setsockopt(s->sock, SOL_SOCKET, SO_REUSEPORT, &optval, sizeof(optval)));
    int addr_ret = inet_pton(AF_INET, sconnect_ip, &(sin.sin_addr));
    sin.sin_family = AF_INET;
    sin.sin_port = htons(port);
    if(!addr_ret) {
      eprintf("Invalid connect IP ('%s') selected!\n", sconnect_ip);
      ret = RC_ERROR;
      goto out;
    }
    if(connect(s->sock, (const struct sockaddr *)&sin, sizeof(sin))) {
      perror("serial2framed_tcp: connect()");
      eprintf("serial2framed_tcp: IP: %s port: %d\n", sconnect_ip, port);
      ret = RC_ERROR;
      goto out;
    }
    s->ev = event_new(base, s->sock, EV_READ | EV_PERSIST, event_handler, s);
    event_add(s->ev, &tv_sock_read_timeout);
  }

out:
  *sess = (void *)s;
  return ret;
}

static int serial2framed_tcp_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s *)sess;
  struct pad_s *pads;
  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  if(!strcmp(plist->name, "serial_framed_tcp")) {
    litex_sim_module_pads_get(pads, "sink_data", (void **)&s->rx);
    assert(s->rx);
    litex_sim_module_pads_get(pads, "sink_valid", (void **)&s->rx_valid);
    assert(s->rx_valid);
    litex_sim_module_pads_get(pads, "sink_ready", (void **)&s->rx_ready);
    assert(s->rx_ready);

    litex_sim_module_pads_get(pads, "source_data", (void **)&s->tx);
    assert(s->tx);
    litex_sim_module_pads_get(pads, "source_valid", (void **)&s->tx_valid);
    assert(s->tx_valid);
    litex_sim_module_pads_get(pads, "source_ready", (void **)&s->tx_ready);
    assert(s->tx_ready);

    // optional
    litex_sim_module_pads_get(pads, "sink_first", (void **)&s->rx_first);
    litex_sim_module_pads_get(pads, "sink_last", (void **)&s->rx_last);

    litex_sim_module_pads_get(pads, "source_first", (void **)&s->tx_first);
    litex_sim_module_pads_get(pads, "source_last", (void **)&s->tx_last);
  }

  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void **)&s->sys_clk);

out:
  return ret;
}


static int tx_is_first(struct session_s *s)
{
  static int prev_tx_valid = 0;
  int res;
  if(s->tx_first) {
    res = *s->tx_first;
  } else {
    res = !prev_tx_valid && *s->tx_valid;
  }
  prev_tx_valid = *s->tx_valid;
  return res;
}

static int tx_is_last_or_last_plus_one(struct session_s *s)
{
  static int prev_tx_valid = 0;
  int res;
  if(s->tx_last) {
    res = *s->tx_last;
  } else {
    res = prev_tx_valid && !*s->tx_valid;
  }
  prev_tx_valid = *s->tx_valid;
  return res;
}

static int serial2framed_tcp_tick(void *sess, uint64_t time_ps)
{
  static clk_edge_state_t edge;
  char c;
  int ret = RC_OK;
  ssize_t sent_sz = -1;
  struct tcp_packet_s *ptp;

  struct session_s *s = (struct session_s *)sess;
  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  *s->tx_ready = 1;
  if(tx_is_first(s)) {
    s->datalen = 0;
  }
  if(*s->tx_valid == 1) {
    c = *s->tx;
    s->databuf[s->datalen++] = c;
  }
  if(tx_is_last_or_last_plus_one(s)) {
    assert(s->datalen > 0); // streams can't represent zero length packet
    char sendbuf[MAX_PACKET_LEN + sizeof(uint32_t)];
    uint32_t net_sz = htonl(s->datalen);
    memcpy(sendbuf, &net_sz, sizeof(uint32_t));
    memcpy(sendbuf + sizeof(uint32_t), s->databuf, s->datalen);
#ifdef DEBUG
    hexdump("d2h_raw", s->databuf, s->datalen);
#endif
    sent_sz = send(s->sock, sendbuf, s->datalen + sizeof(uint32_t), 0);
    if(sent_sz != s->datalen + sizeof(uint32_t)) {
      perror("serial2framed_tcp: send()");
      event_base_loopexit(base, NULL);
      return RC_ERROR;
    }
    s->datalen = 0;
  }

  *s->rx_valid = 0;
  if(s->rx_first)
    *s->rx_first = 0;
  if(s->rx_last)
    *s->rx_last = 0;
  if(s->inlen) {
    *s->rx_valid = 1;
    *s->rx = s->inbuf[s->insent];
    if(s->insent == 0) {
      if(s->rx_first)
        *s->rx_first = 1;
    }
    if(*s->rx_ready == 1) {
      s->insent++;
    }
    if(s->insent == s->inlen) {
      s->insent = 0;
      s->inlen = 0;
      if(s->rx_last)
        *s->rx_last = 1;
    }
  } else {
    if(s->tcppack) {
      memcpy(s->inbuf, s->tcppack->data, s->tcppack->len);
      s->inlen = s->tcppack->len;
      ptp = s->tcppack->next;
      free(s->tcppack);
      s->tcppack = ptp;
    }
  }

  return ret;
}

// clang-format off
static struct ext_module_s ext_mod = {
  "serial2framed_tcp",
  serial2framed_tcp_start,
  serial2framed_tcp_new,
  serial2framed_tcp_add_pads,
  NULL, // stop
  serial2framed_tcp_tick
};
// clang-format on

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}

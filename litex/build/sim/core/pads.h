/* Copyright (C) 2017 LambdaConcept */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

struct pad_s {
  char *name;
  size_t len;
  void *signal;
};

struct pad_list_s {
  char *name;
  struct pad_s *pads;
  int index;
  struct pad_list_s *next;
};

int litex_sim_pads_get_list(struct pad_list_s **plist);
int litex_sim_pads_find(struct pad_list_s *first, char *name, int index,  struct pad_list_s **found);
int litex_sim_register_pads(struct pad_s *pads, char *interface_name, int index);

#ifdef __cplusplus
} // extern "C"
#endif

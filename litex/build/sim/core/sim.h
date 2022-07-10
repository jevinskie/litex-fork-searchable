#pragma once

#include "modules.h"

#ifdef __cplusplus
extern "C" {
#endif

struct session_list_s {
  void *session;
  char tickfirst;
  struct ext_module_s *module;
  struct session_list_s *next;
};

extern struct session_list_s *sesslist;

#ifdef __cplusplus
} // extern "C"
#endif

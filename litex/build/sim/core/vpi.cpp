#include "vpi.h"
// #include "Vsim_fake.h"

struct Vsim {
  uint8_t foo;
  void eval() {};
};

uint64_t main_time = 0;
Vsim *g_sim = nullptr;

extern "C" void litex_sim_eval(void *vsim, uint64_t time_ps)
{
  Vsim *sim = (Vsim*)vsim;
  sim->eval();
  main_time = time_ps;
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
}

extern "C" void litex_sim_init_tracer(void *vsim, long start, long end)
{
}

extern "C" void litex_sim_tracer_dump()
{
}

extern "C" int litex_sim_got_finish()
{
  return 0;
}

#if VM_COVERAGE
extern "C" void litex_sim_coverage_dump()
{
}
#endif

double sc_time_stamp()
{
  return main_time;
}

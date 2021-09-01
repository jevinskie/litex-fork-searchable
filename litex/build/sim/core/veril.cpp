/* Copyright (C) 2017 LambdaConcept */

#include <algorithm>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "Vsim.h"
#include "verilated.h"
#ifdef TRACE_FST
#include "verilated_fst_c.h"
#else
#include "verilated_vcd_c.h"
#endif

#ifdef TRACE_FST
VerilatedFstC* tfp;
#else
VerilatedVcdC* tfp;
#endif
uint64_t tfp_start;
uint64_t tfp_end;
int tfp_cycles = -1;
uint64_t main_time = 0;
Vsim *g_sim = nullptr;

static int g_last_dump_state = -1;
static int g_dump_state = -1;
static int g_trace_exit = 0;
static uint64_t g_trace_time_start = -1;
static uint64_t g_trace_time_end = -1;
static uint64_t g_trace_time = -1;


extern "C" void litex_sim_eval(void *vsim, uint64_t time_ps)
{
  Vsim *sim = (Vsim*)vsim;
  sim->eval();
  main_time = time_ps;
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_tracer(void *vsim, long start, long end, int cycles, int trace_exit)
{
  Vsim *sim = (Vsim*)vsim;
  tfp_start = start;
  tfp_end = end >= 0 ? end : UINT64_MAX;
  tfp_cycles = cycles;
  g_trace_exit = trace_exit;
  Verilated::traceEverOn(true);
#ifdef TRACE_FST
      tfp = new VerilatedFstC;
      sim->trace(tfp, 99);
      #define TRACE_FILE "sim.fst"
#else
      tfp = new VerilatedVcdC;
      #define TRACE_FILE "sim.vcd"
#endif
  sim->trace(tfp, 99);
  tfp->set_time_unit("1ps");
  tfp->set_time_resolution("1ps");
  tfp->open(TRACE_FILE);
#undef TRACE_FILE
  g_sim = sim;
}

extern "C" void litex_sim_tracer_dump()
{
  static int last_enabled = 0;
  static int cycles_dumped = 0;
  bool dump_enabled = true;

  if (g_sim != nullptr) {
    dump_enabled = g_sim->sim_trace != 0 ? true : false;
    if (last_enabled == 0 && dump_enabled) {
      printf("<DUMP ON>\n");
      fflush(stdout);
      cycles_dumped = 0;
      g_trace_time_start = main_time;
    } else if (last_enabled == 1 && !dump_enabled) {
      printf("<DUMP OFF>\n");
      fflush(stdout);
      tfp->flush();
//      g_trace_time_end = main_time;
    }
    last_enabled = (int) dump_enabled;
  }


  // fprintf(stderr, "q de: %d le: %d s: %llu e: %llu now: %llu\n", dump_enabled, last_enabled, tfp_start, tfp_end, main_time);
  if (dump_enabled) {
    bool triggered = false;
    if (tfp_cycles < 0) {
        triggered = tfp_start <= main_time && main_time <= tfp_end;
    } else {
        triggered = tfp_start <= main_time && cycles_dumped <= tfp_cycles;
    }
    if (triggered) {
        g_dump_state = 0;
        // fprintf(stderr, "Q");
        uint64_t fake_time = main_time;
        if (g_trace_time_end +1 != 0) {
            int64_t delta = (int64_t)(g_trace_time_start - g_trace_time_end);
            int64_t min_gap = 1000000 * 100; // 100 microsecond gap
            if (delta > min_gap) {
                delta -= min_gap;
            }
            fake_time -= delta;
        }
        tfp->dump((vluint64_t) fake_time);
        ++cycles_dumped;
    }
  }
  bool ended = false;
  if (tfp_cycles < 0) {
    ended = main_time > tfp_end;
  } else {
    ended = cycles_dumped > tfp_cycles;
  }
  if (ended) {
    g_dump_state =  1;
  }
  if (g_last_dump_state != g_dump_state) {
    if (g_dump_state == 0) {
      printf("<DUMP START>\n");
      fflush(stdout);
      cycles_dumped = 0;
      g_trace_time_start = main_time;
    } else if (g_dump_state == 1) {
      printf("<DUMP END>\n");
      fflush(stdout);
      tfp->flush();
      g_trace_time_end = main_time;
    }
  }
  g_last_dump_state = g_dump_state;
}

extern "C" int litex_sim_got_finish()
{
  return Verilated::gotFinish() || (g_trace_exit && g_last_dump_state == 1);
}

#if VM_COVERAGE
extern "C" void litex_sim_coverage_dump()
{
  VerilatedCov::write("sim.cov");
}
#endif

double sc_time_stamp()
{
  return main_time;
}

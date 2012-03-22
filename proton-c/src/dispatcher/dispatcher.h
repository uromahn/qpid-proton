#ifndef _PROTON_DISPATCHER_H
#define _PROTON_DISPATCHER_H 1

/*
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 *
 */

#include <sys/types.h>
#include <stdbool.h>
#include <proton/value.h>

typedef struct pn_dispatcher_t pn_dispatcher_t;

typedef void (pn_action_t)(pn_dispatcher_t *disp);

#define SCRATCH (1024)

struct pn_dispatcher_t {
  pn_action_t *actions[256];
  const char *names[256];
  uint8_t frame_type;
  pn_trace_t trace;
  uint16_t channel;
  uint8_t code;
  pn_list_t *args;
  char *payload;
  size_t size;
  pn_list_t *output_args;
  const char *output_payload;
  size_t output_size;
  size_t capacity;
  size_t available;
  char *output;
  void *context;
  char scratch[SCRATCH];
};

pn_dispatcher_t *pn_dispatcher(uint8_t frame_type, void *context);
void pn_dispatcher_destroy(pn_dispatcher_t *disp);
void pn_dispatcher_action(pn_dispatcher_t *disp, uint8_t code, const char *name,
                          pn_action_t *action);
void pn_init_frame(pn_dispatcher_t *disp);
void pn_field(pn_dispatcher_t *disp, int index, pn_value_t arg);
void pn_append_payload(pn_dispatcher_t *disp, const char *data, size_t size);
void pn_post_frame(pn_dispatcher_t *disp, uint16_t ch, uint32_t performative);
ssize_t pn_dispatcher_input(pn_dispatcher_t *disp, char *bytes, size_t available);
ssize_t pn_dispatcher_output(pn_dispatcher_t *disp, char *bytes, size_t size);

#endif /* dispatcher.h */
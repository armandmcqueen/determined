# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""A Python interface for creating TensorFlow servers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.core.framework import device_attributes_pb2
from tensorflow.python import pywrap_tensorflow


################################################################################
#####################            DET_DEBUG             #########################
################################################################################
from google.protobuf import text_format
import os

def read_envvar_bool(envvar_name):
    print(f"Reading envvar {envvar_name}={os.environ.get(envvar_name)}")
    return os.environ.get(envvar_name, default="false").lower() == "true"


def print_session_config(log_location_id, session_config):
    config_proto_as_str = text_format.MessageToString(session_config, as_one_line=True)
    print("HOTPATCH", f"session_config at {log_location_id} (device_lib_hotpatch):",
          "|", config_proto_as_str, "|")

def print_run_config(log_location_id, run_config):
    run_config_as_str = str(vars(run_config))
    print("HOTPATCH", f"run_config at {log_location_id} (device_lib_hotpatch):",
          "|", run_config_as_str, "|")


DISPLAY_SESSION_CONFIG = read_envvar_bool("DET_DEBUG_TRACK_SESSION_CONFIG")
DISPLAY_RUN_CONFIG = read_envvar_bool("DET_DEBUG_TRACK_RUN_CONFIG")
VERBOSE_CUSTOM_LOGGING = read_envvar_bool("DET_DEBUG_VERBOSE_CUSTOM_LOGGING")

print("HOTPATCH", "device_lib_hotpatch.py", f"DISPLAY_SESSION_CONFIG = {DISPLAY_SESSION_CONFIG}")
print("HOTPATCH", "device_lib_hotpatch.py", f"DISPLAY_RUN_CONFIG = {DISPLAY_RUN_CONFIG}")
print("HOTPATCH", "device_lib_hotpatch.py", f"VERBOSE_CUSTOM_LOGGING = {VERBOSE_CUSTOM_LOGGING}")


def hprint(s):
    if VERBOSE_CUSTOM_LOGGING:
        print("HOTPATCH", "device_lib_hotpatch", "custom logs:", s)

################################################################################

def list_local_devices(session_config=None):
  """List the available devices available in the local process.

  Args:
    session_config: a session config proto or None to use the default config.

  Returns:
    A list of `DeviceAttribute` protocol buffers.
  """
  def _convert(pb_str):
    m = device_attributes_pb2.DeviceAttributes()
    m.ParseFromString(pb_str)
    return m

  return [
      _convert(s)
      for s in pywrap_tensorflow.list_devices(session_config=session_config)
  ]

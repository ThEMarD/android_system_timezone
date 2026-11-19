# Copyright 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
import sys

"""Shared functions for use in tzdata scripts."""

def GetIanaTarFile(dir_name, file_prefix):
  matching_files = []
  for filename in os.listdir(dir_name):
    if filename.startswith(file_prefix) and filename.endswith('.tar.gz'):
      matching_files.append(filename);

  if len(matching_files) == 0:
    return None
  elif len(matching_files) == 1:
    return '%s/%s' % (dir_name, matching_files[0])
  else:
    print('Multiple %s files found unexpectedly %s' % (file_prefix, matching_files))
    sys.exit(1)


def InvokeSoong(android_build_top, build_modules):
  """Makes sure the specified host modules have been built.

  If ANDROID_TZ_HOST_TOOLS is set, it is taken to be a directory holding the
  host binaries (normally ${ANDROID_HOST_OUT}/bin) and Soong is not invoked at
  all. This lets the update scripts run on hosts where soong_ui cannot be
  configured, and it is also the only way to short-circuit the check in the
  subprocesses these scripts start (create-tz_version.py, create-test-data.sh),
  which do not inherit an in-process shim from the caller.
  """
  prebuilt_dir = os.environ.get('ANDROID_TZ_HOST_TOOLS')
  if prebuilt_dir:
    missing = [module for module in build_modules
               if not os.path.isfile(os.path.join(prebuilt_dir, module))]
    if missing:
      print('ERROR: %s does not contain: %s' % (prebuilt_dir, ', '.join(missing)))
      sys.exit(1)
    print('Using prebuilt host tools from %s, skipping Soong' % prebuilt_dir)
    return

  old_cwd = os.getcwd()
  os.chdir(android_build_top)
  subprocess.check_call(['build/soong/soong_ui.bash', '--make-mode', '-j30'] + build_modules)
  os.chdir(old_cwd)

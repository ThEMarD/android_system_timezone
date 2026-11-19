#!/usr/bin/python3 -B

# Copyright 2023 The Android Open Source Project
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

""" Applies Android release specific patches to IANA tzdata archives. """

import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.append('%s/external/icu/tools' % os.environ.get('ANDROID_BUILD_TOP'))
import i18nutil
import tzdatautil

android_build_top = i18nutil.GetAndroidRootOrDie()
timezone_dir = os.path.realpath('%s/system/timezone' % android_build_top)
i18nutil.CheckDirExists(timezone_dir, 'system/timezone')

timezone_input_data_dir = os.path.realpath('%s/input_data' % timezone_dir)
iana_input_data_dir = os.path.realpath('%s/iana' % timezone_input_data_dir)
iana_original_input_data_dir = os.path.realpath('%s/original' % iana_input_data_dir)
patches_dir = os.path.realpath('%s/patches' % iana_input_data_dir)
iana_patched_data_dir = os.path.realpath('%s/patched' % iana_input_data_dir)


def extractTar(tar_file, dir):
  with tarfile.open(tar_file, 'r') as tar:
    try:
      tar.extractall(dir, filter='data')
    except TypeError:
      # "filter" was added in Python 3.11.4; older interpreters have no
      # equivalent, so fall back to the unguarded extraction they support.
      tar.extractall(dir)

def applyPatchesTo(patches_dir, dest_dir):
  print("Applying patches from %s to %s" % (patches_dir, dest_dir))

  p = re.compile('\\d+-(.*)\\.patch')
  was_patched = False

  # Sorted so the numeric file name prefixes decide the order the patches are
  # applied in, and so the patched archive stays reproducible: os.listdir()
  # returns directory order, which is not specified.
  for patch_file in sorted(os.listdir(patches_dir)):
    m = p.match(patch_file)
    if not m:
      continue
    file_to_patch_path = '%s/%s' % (dest_dir, m.group(1))
    patch_path = '%s/%s' % (patches_dir, patch_file)
    # --batch stops patch from prompting (an unattended run would hang) and
    # --forward makes an already applied patch an error instead of applying it
    # backwards. --no-backup-if-mismatch matters because the Android patches
    # apply with line offsets: without it patch leaves a *.orig copy of the
    # file behind, and that copy would be packed into the patched archive.
    ret_code = subprocess.call(['patch', '--batch', '--forward',
                                '--no-backup-if-mismatch',
                                file_to_patch_path, patch_path])
    if ret_code != 0:
      sys.exit('Failed to apply %s. Halting' % patch_path)
    was_patched = True
  return was_patched


def repack(temp_dir, dest):
  print("packing %s into %s" % (temp_dir, dest))

  # To make sure that repeated run generates the same archive: tar records the
  # modification time of every entry, so normalize all of them, including any
  # in subdirectories.
  for root_dir, dir_names, file_names in os.walk(temp_dir):
    for name in dir_names + file_names:
      os.utime(os.path.join(root_dir, name), (0, 0))

  # This command is taken from eggert/tz Makefile.
  tar_command = ("tar --format=pax --pax-option='delete=atime,delete=ctime'"
                 " --numeric-owner --owner=0 --group=0 --mode=go+u,go-w"
                 " --sort=name -cf - * | gzip -9n > %s" % shlex.quote(dest))
  ret_code = subprocess.call(tar_command, shell=True, cwd=temp_dir)
  if ret_code != 0:
    sys.exit('Failed to repack patched files. Halting')


# Returns the path to the archive that tzdata files should be generated from:
# the patched archive when there are patches, the original one otherwise.
def Apply():
  iana_data_tar_file = tzdatautil.GetIanaTarFile(iana_original_input_data_dir, 'tzdata')

  # Work in a directory of our own: a temporary directory reused across runs
  # would keep files left over from a previous run out of the patch or the
  # archive.
  temp_dir = tempfile.mkdtemp("-tzdata")
  try:
    extractTar(iana_data_tar_file, temp_dir)

    # There should be one single file only and it is always created anew if
    # patches are available.
    for filename in os.listdir(iana_patched_data_dir):
      path = '%s/%s' % (iana_patched_data_dir, filename)
      if os.path.isfile(path):
        os.remove(path)

    was_patched = applyPatchesTo(patches_dir, temp_dir)
    if was_patched:
      archive_name = os.path.basename(iana_data_tar_file)
      patched_data_tar_file = '%s/%s' % (iana_patched_data_dir, archive_name)
      repack(temp_dir, patched_data_tar_file)
      return patched_data_tar_file
    else:
      return iana_data_tar_file
  finally:
    shutil.rmtree(temp_dir, ignore_errors=True)

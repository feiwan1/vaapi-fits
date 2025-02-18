###
### Copyright (C) 2021 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import slash

from ....lib.common import get_media
from ....lib.ffmpeg.qsv.util import *
from ....lib.mfx.runtime import MFXRuntimeTest

@slash.requires(have_ffmpeg)
@slash.requires(*have_ffmpeg_hwaccel("qsv"))
@slash.requires(using_compatible_driver)
class detect(MFXRuntimeTest):
  def before(self):
    super().before()
    self.renderDevice = get_media().render_device

  def test(self):
    self.check(
      "ffmpeg -nostats -v verbose"
      " -init_hw_device qsv=qsv:hw_any,child_device={renderDevice}"
      " -hwaccel qsv"
      " -f lavfi -i yuvtestsrc"
      " -f null /dev/null".format(**vars(self))
    )

###
### Copyright (C) 2022 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import os
import slash

from ....lib.gstreamer.encoderbase import BaseEncoderTest, Encoder as GstEncoder
from ....lib.gstreamer.util import have_gst_element
from ....lib.gstreamer.va.util import mapprofile, map_best_hw_format, mapformat
from ....lib.gstreamer.va.decoder import Decoder
from ....lib.common import get_media, mapRangeInt

class Encoder(GstEncoder):
  @property
  def hwformat(self):
    return map_best_hw_format(super().format, self.props["caps"]["fmts"])

  @property
  def format(self):
    return mapformat(super().format)

  @property
  def rcmode(self):
    if self.codec in ["jpeg"]:
      return ""
    return f" rate-control={super().rcmode}"

  @property
  def qp(self):
    def inner(qp):
      if self.codec in ["mpeg2"]:
        mqp = mapRangeInt(qp, [0, 100], [0, 51])
        return f" qpi={mqp} qpp={mqp} qpb={mqp}"
      if self.codec in ["vp8", "vp9"]:
        return f" qpi={qp}"
      return f" qpi={qp} qpp={qp} qpb={qp}"
    return self.ifprop("qp", inner)

  @property
  def quality(self):
    def inner(quality):
      if self.codec in ["jpeg"]:
        return f" quality={quality}"
      return f" target-usage={quality}"
    return self.ifprop("quality", inner)

  @property
  def minrate(self):
    if super().rcmode in ["vbr"]:
      tp = self.props["minrate"] / self.props["maxrate"]
      return f" target-percentage={int(tp * 100)}"
    return ""

  gop     = property(lambda s: s.ifprop("gop", " key-int-max={gop}"))
  slices  = property(lambda s: s.ifprop("slices", " num-slices={slices}"))
  bframes = property(lambda s: s.ifprop("bframes", " b-frames={bframes}"))
  maxrate = property(lambda s: s.ifprop("maxrate", " bitrate={maxrate}"))
  refmode = property(lambda s: s.ifprop("refmode", " ref-pic-mode={refmode}"))
  refs    = property(lambda s: s.ifprop("refs", " ref-frames={refs}"))
  loopshp = property(lambda s: s.ifprop("loopshp", " sharpness-level={loopshp}"))
  looplvl = property(lambda s: s.ifprop("looplvl", " loop-filter-level={looplvl}"))

  @property
  def gstencoder(self):
    return (
      f"{super().gstencoder}"
      f"{self.rcmode}{self.gop}{self.qp}"
      f"{self.quality}{self.slices}{self.bframes}"
      f"{self.minrate}{self.maxrate}{self.refmode}{self.refs}"
      #f"{self.lowpower}{self.loopshp}{self.looplvl}", gst-va not support lowpoer and vp8/vp9 enc
    )

@slash.requires(*have_gst_element("va"))
class EncoderTest(BaseEncoderTest):
  EncoderClass = Encoder
  DecoderClass = Decoder

  def before(self):
    super().before()
    os.environ["GST_VA_DRM_DEVICE"] = get_media().render_device

  def map_profile(self):
    return mapprofile(self.codec, self.profile)

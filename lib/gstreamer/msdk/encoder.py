###
### Copyright (C) 2018-2021 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import os
import slash

from ....lib.gstreamer.encoderbase import BaseEncoderTest, Encoder as GstEncoder
from ....lib.gstreamer.util import have_gst_element
from ....lib.gstreamer.msdk.util import using_compatible_driver, mapprofile, map_best_hw_format, mapformat
from ....lib.gstreamer.msdk.decoder import Decoder
from ....lib.common import get_media, mapRangeInt

class Encoder(GstEncoder):
  @property
  def hwformat(self):
    ifmts = self.props["caps"]["fmts"]
    if self.codec not in ["hevc-8", "vp9"]:
      ifmts = list(set(ifmts) - set(["AYUV"]))
    return map_best_hw_format(super().format, ifmts)

  @property
  def format(self):
    return mapformat(super().format)

  @property
  def rcmode(self):
    if self.codec in ["jpeg"]:
      return ""
    return f" rate-control={super().rcmode} hardware=true"

  @property
  def qp(self):
    def inner(qp):
      if self.codec in ["mpeg2"]:
        mqp = mapRangeInt(qp, [0, 100], [0, 51])
        return f" qpi={mqp} qpp={mqp} qpb={mqp}"
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
  def maxrate(self):
    if super().rcmode in ["vbr"]:
      return f" max-vbv-bitrate={self.props['maxrate']}"
    return ""

  gop     = property(lambda s: s.ifprop("gop", " gop-size={gop}"))
  slices  = property(lambda s: s.ifprop("slices", " num-slices={slices}"))
  bframes = property(lambda s: s.ifprop("bframes", " b-frames={bframes}"))
  minrate = property(lambda s: s.ifprop("minrate", " bitrate={minrate}"))
  refmode = property(lambda s: s.ifprop("refmode", " ref-pic-mode={refmode}"))
  refs    = property(lambda s: s.ifprop("refs", " ref-frames={refs}"))
  ladepth = property(lambda s: s.ifprop("ladepth", " rc-lookahead={ladepth}"))
  tilecols = property(lambda s: s.ifprop("tilecols", " num-tile-cols={tilecols}"))
  tilerows = property(lambda s: s.ifprop("tilerows", " num-tile-rows={tilerows}"))

  @property
  def gstencoder(self):
    return (
      f"{super().gstencoder}"
      f"{self.rcmode}{self.gop}{self.qp}"
      f"{self.quality}{self.slices}{self.tilecols}{self.tilerows}{self.bframes}"
      f"{self.maxrate}{self.minrate}{self.refmode}"
      f"{self.refs}{self.lowpower}{self.ladepth}"
    )

@slash.requires(*have_gst_element("msdk"))
@slash.requires(using_compatible_driver)
class EncoderTest(BaseEncoderTest):
  EncoderClass = Encoder
  DecoderClass = Decoder

  def before(self):
    super().before()
    os.environ["GST_MSDK_DRM_DEVICE"] = get_media().render_device

  def map_profile(self):
    return mapprofile(self.codec, self.profile)

  def validate_caps(self):
    if self.rcmode in ['cbr','vbr','cbr_lp','vbr_lp']:
    # "brafames", if specified, overrides "frames" for bitrate control modes
      self.frames = vars(self).get("brframes", self.frames)
    super().validate_caps()

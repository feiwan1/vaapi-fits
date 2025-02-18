###
### Copyright (C) 2019 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

from ....lib import *
from .util import *

@slash.requires(have_ffmpeg)
@slash.requires(*have_ffmpeg_hwaccel("qsv"))
@slash.requires(*have_ffmpeg_filter("vpp_qsv"))
@slash.requires(using_compatible_driver)
class VppTest(slash.Test, BaseFormatMapper):
  def before(self):
    self.refctx = []
    self.renderDevice = get_media().render_device
    self.post_validate = lambda: None

  def gen_input_opts(self):
    if self.vpp_op not in ["deinterlace"]:
      opts = "-f rawvideo -pix_fmt {mformat} -s:v {width}x{height}"
    else:
      opts = "-c:v {ffdecoder}"
    opts += f" -i {filepath2os(self.source)}"

    return opts

  def gen_output_opts(self):
    vfilter = []
    if self.vpp_op in ["composite"]:
      opts = "-filter_complex"

      vfilter.append("color=black:size={owidth}x{oheight}")
      vfilter.append("format={ihwformat}|qsv")
      vfilter.append("hwupload=extra_hw_frames=16")

      for n, comp in enumerate(self.comps):
        vfilter[-1] += "[out{n}];[0:v]format={ihwformat}|qsv".format(n = n, **vars(self))
        vfilter.append(
          "hwupload=extra_hw_frames=16[in{n}];"
          "[out{n}][in{n}]overlay_qsv=x={x}:y={y}:alpha={alpha}"
          "".format(n = n, alpha = mapRangeInt(comp["a"], [0., 1.], [0, 255]), **comp)
        )
    else:
      opts = "-vf"

      if self.vpp_op not in ["csc"]:
        vfilter.append("format={ihwformat}|qsv")
      vfilter.append("hwupload=extra_hw_frames=16")
      vfilter.append(
        dict(
          brightness  = "vpp_qsv=procamp=1:brightness={mlevel}",
          contrast    = "vpp_qsv=procamp=1:contrast={mlevel}",
          hue         = "vpp_qsv=procamp=1:hue={mlevel}",
          saturation  = "vpp_qsv=procamp=1:saturation={mlevel}",
          denoise     = "vpp_qsv=denoise={mlevel}",
          scale       = "vpp_qsv=w={scale_width}:h={scale_height}",
          scale_qsv   = "scale_qsv=w={scale_width}:h={scale_height}",
          sharpen     = "vpp_qsv=detail={mlevel}",
          deinterlace = "vpp_qsv=deinterlace={mmethod}",
          csc         = "vpp_qsv=format={ohwformat}",
          transpose   = "vpp_qsv=transpose={direction}",
        )[self.vpp_op]
      )

    vfilter.append("hwdownload")
    vfilter.append("format={ohwformat}")

    opts += " '{}'".format(",".join(vfilter))
    if self.vpp_op not in ["csc"]:
      opts += " -pix_fmt {mformat}"
    opts += " -f rawvideo -vsync passthrough -an -vframes {frames} -y {osdecoded}"

    return opts

  def gen_name(self):
    name = "{case}_{vpp_op}"
    name += dict(
      brightness  = "_{level}_{width}x{height}_{format}",
      contrast    = "_{level}_{width}x{height}_{format}",
      hue         = "_{level}_{width}x{height}_{format}",
      saturation  = "_{level}_{width}x{height}_{format}",
      denoise     = "_{level}_{width}x{height}_{format}",
      scale       = "_{scale_width}x{scale_height}_{format}",
      scale_qsv   = "_{scale_width}x{scale_height}_{format}",
      sharpen     = "_{level}_{width}x{height}_{format}",
      deinterlace = "_{method}_{rate}_{width}x{height}_{format}",
      csc         = "_{width}x{height}_{format}_to_{csc}",
      transpose   = "_{degrees}_{method}_{width}x{height}_{format}",
      composite   = "_{owidth}x{oheight}_{format}",
    )[self.vpp_op]

    if vars(self).get("r2r", None) is not None:
      name += "_r2r"

    return name

  @timefn("ffmpeg")
  def call_ffmpeg(self, iopts, oopts):
    call(
      f"{exe2os('ffmpeg')}"
      " -init_hw_device qsv=qsv:hw_any,child_device={renderDevice} -hwaccel qsv"
      " -v verbose {iopts} {oopts}".format(renderDevice= self.renderDevice, iopts = iopts, oopts = oopts))

  def validate_caps(self):
    ifmts         = self.caps.get("ifmts", [])
    ofmts         = self.caps.get("ofmts", [])
    self.ifmt     = self.format
    self.ofmt     = self.format if "csc" != self.vpp_op else self.csc
    self.mformat  = self.map_format(self.format)

    # MSDK does not support I420 and YV12 output formats even though
    # iHD supports it.  Thus, msdkvpp can't output it directly (HW).
    ofmts = list(set(ofmts) - set(["I420", "YV12"]))

    if self.mformat is None:
      slash.skip_test("ffmpeg.{format} unsupported".format(**vars(self)))

    if self.vpp_op in ["csc"]:
      self.ihwformat = self.map_format(self.ifmt if self.ifmt in ifmts else None)
      self.ohwformat = self.map_format(self.ofmt if self.ofmt in ofmts else None)
    else:
      self.ihwformat = self.map_best_hw_format(self.ifmt, ifmts)
      self.ohwformat = self.map_best_hw_format(self.ofmt, ofmts)

    if self.ihwformat is None:
      slash.skip_test("{ifmt} unsupported".format(**vars(self)))
    if self.ohwformat is None:
      slash.skip_test("{ofmt} unsupported".format(**vars(self)))

    if self.vpp_op in ["composite"]:
      self.owidth, self.oheight = self.width, self.height
      for comp in self.comps:
        self.owidth = max(self.owidth, self.width + comp['x'])
        self.oheight = max(self.oheight, self.height + comp['y'])

    self.post_validate()

  def vpp(self):
    self.validate_caps()

    iopts         = self.gen_input_opts()
    oopts         = self.gen_output_opts()
    name          = self.gen_name().format(**vars(self))

    self.decoded = get_media()._test_artifact("{}.yuv".format(name))
    self.osdecoded = filepath2os(self.decoded)
    self.call_ffmpeg(iopts.format(**vars(self)), oopts.format(**vars(self)))

    if vars(self).get("r2r", None) is not None:
      assert type(self.r2r) is int and self.r2r > 1, "invalid r2r value"
      md5ref = md5(self.decoded)
      get_media()._set_test_details(md5_ref = md5ref)

      for i in range(1, self.r2r):
        self.decoded = get_media()._test_artifact("{}_{}.yuv".format(name, i))
        self.osdecoded = filepath2os(self.decoded)
        self.call_ffmpeg(iopts.format(**vars(self)), oopts.format(**vars(self)))
        result = md5(self.decoded)
        get_media()._set_test_details(**{ "md5_{:03}".format(i) : result})
        assert result == md5ref, "r2r md5 mismatch"
        #delete output file after each iteration
        get_media()._purge_test_artifact(self.decoded)
    else:
      self.check_metrics()

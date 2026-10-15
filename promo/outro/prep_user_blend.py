import bpy, sys
src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene
c = s.cycles
c.device = "GPU"            # falls back to the CPU when no GPU is switched on in Preferences
c.samples = 512
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.01
c.adaptive_min_samples = 32
c.use_denoising = True
c.denoiser = "OPENIMAGEDENOISE"
c.denoising_prefilter = "ACCURATE"
c.use_light_tree = True
s.render.use_motion_blur = True
s.render.motion_blur_shutter = 0.5
s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1920, 1080, 100
s.frame_start, s.frame_end = 1, 210
r = s.render
try:
    r.image_settings.media_type = "VIDEO"      # Blender 5
except Exception as e:
    print("media_type:", e)
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
r.ffmpeg.ffmpeg_preset = "BEST" if "BEST" in [i.identifier for i in r.ffmpeg.bl_rna.properties["ffmpeg_preset"].enum_items] else r.ffmpeg.ffmpeg_preset
r.ffmpeg.audio_codec = "NONE"
r.filepath = "//CopyThat_outro_"
bpy.context.preferences.filepaths.use_relative_paths = True
bpy.ops.wm.save_as_mainfile(filepath=dst, compress=True, relative_remap=True)
print("SAVED", dst, r.image_settings.file_format, r.ffmpeg.format, r.ffmpeg.codec, r.ffmpeg.constant_rate_factor, r.ffmpeg.ffmpeg_preset, c.samples, c.device)

from type_read_functions import u32_to_le_hex
from rig_components import components

def log_animation_header(animation_header):
	print(
		"Animation header:",
		f"\tframes: {animation_header["frame_count"]}",
		f"\tstatic scaled bones: {animation_header["static_scale_control_map_pointer"].length}",
		f"\tstatic rotated bones: {animation_header["static_rotation_control_map_pointer"].length}",
		f"\tstatic translated bones: {animation_header["static_translation_control_map_pointer"].length}",
		f"\tanimated scaled bones: {animation_header["animated_scale_control_map_pointer"].length}",
		f"\tanimated rotated bones: {animation_header["animated_rotation_control_map_pointer"].length}",
		f"\tanimated translated bones: {animation_header["animated_translation_control_map_pointer"].length}",
		f"\tanimation hash: {u32_to_le_hex(animation_header["animation_hash"])}",
		f"\tnode count: {animation_header["node_count"]}",
		f"\trig control count: {animation_header["rig_control_count"]}",
		sep="\n"
	)

def log_runtime_rig_components(tag_array):
	print("Runtime rig components:")

	for comp in tag_array.payload:
		fnv_hash = u32_to_le_hex(comp[0])
		print(f"\thash: {fnv_hash}, count: {comp[1]}")
		if fnv_hash in components:
			component = components[fnv_hash]
			print(f"\t\tstring: {component["string"]}")
			print(f"\t\tcomment: {component["comment"]}")
			print(f"\t\tparent: {component["parent"]}")

def log_static_bones_header(static_bones_header):
	print(
		"Static bones header:",
		f"\tframes: {static_bones_header["frame_count"]}",
		f"\tcodec type: {static_bones_header["codec_type"]}",
		f"\tscale_stream_count: {static_bones_header["scale_stream_count"]}",
		f"\trotation_stream_count: {static_bones_header["rotation_stream_count"]}",
		f"\ttranslation_stream_count: {static_bones_header["translation_stream_count"]}",
		sep="\n"
	)

def log_animated_bones_header(animated_bones_header):
	print(
		"Animated header:",
		f"\tcodec type: {animated_bones_header["codec_type"]}",
		f"\tscale_stream_count: {animated_bones_header["scale_stream_count"]}",
		f"\trotation_stream_count: {animated_bones_header["rotation_stream_count"]}",
		f"\ttranslation_stream_count: {animated_bones_header["translation_stream_count"]}",
		sep="\n"
	)

def log_animation_data(animation_duration_in_frames, animation_duration_in_seconds):
	print(
		"Animation properties:",
		f"\tframes count {animation_duration_in_frames}",
		f"\tduration: {round(animation_duration_in_seconds, 2)} seconds",
		sep="\n"
	)

import sys
import math
import numpy as np

from Tag_array import Tag_array
from type_read_functions import *
from Tiger_pointers import Rel_pointer, Vec_pointer
from parser_log_functions import *
from animation_interpolation import *
from enums import Game_version

SCALE_COMPONENTS = 1
ROTATION_COMPONENTS = 4
COMP_ROTATION_COMPONENTS = 3
TRANSLATION_COMPONENTS = 3


"""
NOTE: reading compressed binary quaternion data as float_s16 matches quaternion components from api
it seems:
	float_s16[0] is quat.w
	float_s16[1] is quat.x
	float_s16[2] is quat.y
so the missing component is always quat.z
NOTE: How to get Z's sign?? Mathematically both z and -z are correct
I assume components[1] lesser bit holds sign 1 for minus, 0 for plus,
but need more statistics
NOTE: Checked of all the data available so it seems to be working
If it does not work this is just the worst coinsidence possible
"""

def decompress_quaternion(components):
	floats = [decode_snorm16(x) for x in components]

	w, x, y = floats
	z = math.sqrt(max(1 - w * w - x * x - y * y, 0))

	if math.fabs(x * x + y * y + z * z + w * w - 1) > 0.001:
		raise Exception(f"quat norm is not close to 1: {x * x + y * y + z * z + w * w}")

	if components[1] & 1 == 1:
		z = -z

	return [x, y, z, w]

def u16_to_s16(u):
	# cut to 16 bit, as python number handling is weird
	u &= 0xFFFF
	# if have sign set -> interpret as negative
	if u & 0x8000:
		return u - 0x10000
	else:
		return u

def unpack_unorm16(value):
	return value / 65535

def unpack_snorm16(value):
	return value / 32767

"""u16 from binary, interpreted as signed 16-bit normalized float"""
def decode_snorm16(u16_value):
	return unpack_snorm16(u16_to_s16(u16_value))

def correct_quantization(value, minimum, extent):
	return value * minimum + extent

def read_animation_file_header(f, offset, game_version):
	padding_1 = { Game_version.D1_ROI: 104, Game_version.D2_SK: 120, Game_version.D2_EOF: 120, Game_version.MARATHON: 120 }
	padding_2 = { Game_version.D1_ROI: 24,  Game_version.D2_SK: 24,  Game_version.D2_EOF: 24,  Game_version.MARATHON: 24  }
	padding_3 = { Game_version.D1_ROI: 20,  Game_version.D2_SK: 24,  Game_version.D2_EOF: 28,  Game_version.MARATHON: 28  }
	padding_4 = { Game_version.D1_ROI: 4,   Game_version.D2_SK: 14,  Game_version.D2_EOF: 10,  Game_version.MARATHON: 10  }

	f.seek(offset)

	file_size = read_u64(f)

	f.seek(8, 1) # 8 bytes of padding

	static_bone_data = Rel_pointer(f)
	animated_bone_data = Rel_pointer(f)
	extra_data = Rel_pointer(f)
	extra_data_2 = Rel_pointer(f)

	f.seek(padding_1[game_version], 1)

	static_scale_control_map_pointer = Vec_pointer(f)
	static_rotation_control_map_pointer = Vec_pointer(f)
	static_translation_control_map_pointer = Vec_pointer(f)
	animated_scale_control_map_pointer = Vec_pointer(f)
	animated_rotation_control_map_pointer = Vec_pointer(f)
	animated_translation_control_map_pointer = Vec_pointer(f)

	f.seek(padding_2[game_version], 1)

	animation_hash = read_u32(f)

	f.seek(padding_3[game_version], 1)

	frame_count = read_u16(f)
	node_count = 0

	if game_version == Game_version.D1_ROI:
		node_count = read_u8(f)
	else:
		node_count = read_u16(f)

	rig_control_count = 0

	if game_version == Game_version.D1_ROI:
		rig_control_count = read_u8(f)
	else:
		rig_control_count = read_u16(f)

	f.seek(padding_4[game_version], 1)

	unk_arr_1_pointer = Vec_pointer(f)
	unk_arr_2_pointer = Vec_pointer(f)
	rig_components_array_pointer = Vec_pointer(f)

	return {
		"file_size": file_size,
		"static_bone_data": static_bone_data,
		"animated_bone_data": animated_bone_data,
		"static_scale_control_map_pointer": static_scale_control_map_pointer,
		"static_rotation_control_map_pointer": static_rotation_control_map_pointer,
		"static_translation_control_map_pointer": static_translation_control_map_pointer,
		"animated_scale_control_map_pointer": animated_scale_control_map_pointer,
		"animated_rotation_control_map_pointer": animated_rotation_control_map_pointer,
		"animated_translation_control_map_pointer": animated_translation_control_map_pointer,
		"animation_hash": animation_hash,
		"frame_count": frame_count,
		"node_count": node_count,
		"rig_control_count": rig_control_count,
		"rig_components_array_pointer": rig_components_array_pointer,
	}

def read_rig_components(f, pointer):
	def read_rig_component(f):
		return read_u32_array(f, 2)

	rig_components_array = Tag_array(f, pointer, read_rig_component)
	return rig_components_array

def parse_control_maps(f, animation_header, game_version):
	functions = { Game_version.D1_ROI: read_u8, Game_version.D2_SK: read_u16, Game_version.D2_EOF: read_u16, Game_version.MARATHON: read_u16 }
	# staic
	static_scale_control_map = Tag_array(f, animation_header["static_scale_control_map_pointer"], functions[game_version])
	static_rotation_control_map = Tag_array(f, animation_header["static_rotation_control_map_pointer"], functions[game_version])
	static_translation_control_map = Tag_array(f, animation_header["static_translation_control_map_pointer"], functions[game_version])
	# animated
	animated_scale_control_map = Tag_array(f, animation_header["animated_scale_control_map_pointer"], functions[game_version])
	animated_rotation_control_map = Tag_array(f, animation_header["animated_rotation_control_map_pointer"], functions[game_version])
	animated_translation_control_map = Tag_array(f, animation_header["animated_translation_control_map_pointer"], functions[game_version])

	return {
		"static_scale_control_map": static_scale_control_map,
		"static_rotation_control_map": static_rotation_control_map,
		"static_translation_control_map": static_translation_control_map,
		"animated_scale_control_map": animated_scale_control_map,
		"animated_rotation_control_map": animated_rotation_control_map,
		"animated_translation_control_map": animated_translation_control_map
	}

# version independent
def read_common_codec_header(f):
	codec_type = read_u16(f)
	scale_stream_count = read_u16(f)
	rotation_stream_count = read_u16(f)
	translation_stream_count = read_u16(f)
	prob_error_calue = read_f32(f)
	prob_compression_rate = read_f32(f)

	return {
		"codec_type": codec_type,
		"scale_stream_count": scale_stream_count,
		"rotation_stream_count": rotation_stream_count,
		"translation_stream_count": translation_stream_count,
		"prob_error_value": prob_error_calue,
		"prob_compression_rate": prob_compression_rate
	}

# version independent
def read_static_bones_header(f, pointer):
	address = pointer.get_address()
	f.seek(address)

	common_header = read_common_codec_header(f)

	if common_header["codec_type"] != 3:
		print(f"Read static header // Error: Static data codec is not type 3, it is: {common_header["codec_type"]}")
		return None

	frame_count = read_u32(f)

	scale_stream_quantization = read_f32_array(f, 2)

	translation_stream_quantization = [read_f32_array(f, 3), read_f32_array(f, 3)]

	f.seek(4, 1) # 4 bytes of padding

	stream = Vec_pointer(f)

	result = {
		"frame_count": frame_count,
		"scale_stream_quantization": scale_stream_quantization,
		"translation_stream_quantization": translation_stream_quantization,
		"stream": stream
	}

	result.update(common_header)

	return result

def parse_static_bones_stream(f, animation_header, static_animation_data):
	print("Parsing static data // Info: Codec 3")

	stream = Tag_array(f, static_animation_data["stream"], read_u16)
	scale_map_length = animation_header["static_scale_control_map_pointer"].length
	rotation_map_length = animation_header["static_rotation_control_map_pointer"].length
	translation_map_length = animation_header["static_translation_control_map_pointer"].length

	offset = 0
	scale_stream_data, offset = stream.read_vec(offset, scale_map_length)
	rotation_stream_data, offset = stream.read_vec(offset, rotation_map_length * ROTATION_COMPONENTS)
	translation_stream_data, offset = stream.read_vec(offset, translation_map_length * TRANSLATION_COMPONENTS)

	scale_stream_quantization = static_animation_data["scale_stream_quantization"]
	translation_stream_quantization = static_animation_data["translation_stream_quantization"]

	scale_stream = [
		correct_quantization(
			unpack_unorm16(x),
			scale_stream_quantization[0],
			scale_stream_quantization[1],
		) for x in scale_stream_data
	]

	rotation_stream = []

	for i in range(rotation_map_length):
		rotation = [
			correct_quantization(
				unpack_unorm16(
					rotation_stream_data[i * ROTATION_COMPONENTS + component_i]
				),
				2,
				-1
			) for component_i in range(ROTATION_COMPONENTS)
		]

		rotation_stream.append(rotation)

	translation_stream = []

	for i in range(translation_map_length):
		translation = [
			correct_quantization(
				unpack_unorm16(
					translation_stream_data[i * TRANSLATION_COMPONENTS + component_i]
				),
				translation_stream_quantization[0][component_i],
				translation_stream_quantization[1][component_i]
			) for component_i in range(TRANSLATION_COMPONENTS)
		]

		translation_stream.append(translation)

	return {
		"scale": scale_stream,
		"rotation": rotation_stream,
		"translation": translation_stream
	}

def parse_animated_codec_3(f, animation_header,  animated_bones_header, control_maps, bone_data):
	print("Parsing animated data // Info: Codec 3")

	stream_data = Tag_array(f, animated_bones_header["stream_pointer"], read_u16)
	scale_map_length = animation_header["animated_scale_control_map_pointer"].length
	rotation_map_length = animation_header["animated_rotation_control_map_pointer"].length
	translation_map_length = animation_header["animated_translation_control_map_pointer"].length

	animated_scale_control_map = control_maps["animated_scale_control_map"]
	animated_rotation_control_map = control_maps["animated_rotation_control_map"]
	animated_translation_control_map = control_maps["animated_translation_control_map"]

	scale_stream_quantization = animated_bones_header["scale_stream_quantization"]
	translation_stream_quantization = animated_bones_header["translation_stream_quantization"]

	frame_count = animated_bones_header["frame_count"]

	stream_offset = 0
	for bone_map_i in range(animated_scale_control_map.length):
		bone_skeleton_i = animated_scale_control_map.read(bone_map_i)

		for frame_i in range(frame_count):
			scale = correct_quantization(
				unpack_unorm16(
					stream_data.read(stream_offset)
				),
				scale_stream_quantization[0],
				scale_stream_quantization[1],
			)

			bone_data[bone_skeleton_i]["scales"].append(scale)
			stream_offset += SCALE_COMPONENTS

	for bone_map_i in range(animated_rotation_control_map.length):
		bone_skeleton_i = animated_rotation_control_map.read(bone_map_i)

		for frame_i in range(frame_count):

			rotation = [
				correct_quantization(
					unpack_unorm16(
						stream_data.read(stream_offset + component_i)
					),
					2,
					-1
				) for component_i in range(ROTATION_COMPONENTS)
			]

			bone_data[bone_skeleton_i]["rotations"].append(rotation)
			stream_offset += ROTATION_COMPONENTS

	for bone_map_i in range(animated_translation_control_map.length):
		bone_skeleton_i = animated_translation_control_map.read(bone_map_i)

		for frame_i in range(frame_count):
			translation = [
				correct_quantization(
					unpack_unorm16(
						stream_data.read(stream_offset + component_i)
					),
					translation_stream_quantization[0][component_i],
					translation_stream_quantization[1][component_i]
				) for component_i in range(TRANSLATION_COMPONENTS)
			]

			bone_data[bone_skeleton_i]["translations"].append(translation)
			stream_offset += TRANSLATION_COMPONENTS

	return True

def read_animated_bones_header(f, pointer):
	address = pointer.get_address()
	f.seek(address)

	common_header = read_common_codec_header(f)

	if common_header["codec_type"] == 0:
		frame_count = read_u64(f)
		scale_stream = Vec_pointer(f)
		rotation_stream = Vec_pointer(f)
		translation_stream = Vec_pointer(f)

		common_header["frame_count"] = frame_count
		common_header["scale_stream"] = scale_stream
		common_header["rotation_stream"] = rotation_stream
		common_header["translation_stream"] = translation_stream

	elif common_header["codec_type"] == 1:
		uncompressed_data = Vec_pointer(f)
		compressed_data = Vec_pointer(f)
		keyframe_deltas = Vec_pointer(f)
		interpolation_data = Vec_pointer(f)
		quantization_minimums = Vec_pointer(f)
		quantization_extents = Vec_pointer(f)
		array_7 = Vec_pointer(f)

		common_header["uncompressed_data"] = uncompressed_data
		common_header["compressed_data"] = compressed_data
		common_header["keyframe_deltas"] = keyframe_deltas
		common_header["interpolation_data"] = interpolation_data
		common_header["quantization_minimums"] = quantization_minimums
		common_header["quantization_extents"] = quantization_extents
		common_header["array_7"] = array_7

	elif common_header["codec_type"] == 2:
		frame_count = read_u64(f)
		stream_data = Vec_pointer(f)
		quantization_minimums = Vec_pointer(f)
		quantization_extents = Vec_pointer(f)

		common_header["frame_count"] = frame_count
		common_header["stream_data"] = stream_data
		common_header["quantization_minimums"] = quantization_minimums
		common_header["quantization_extents"] = quantization_extents
	elif common_header["codec_type"] == 3:
		frame_count = read_u32(f)

		scale_stream_quantization = read_f32_array(f, 2)

		translation_stream_quantization = [read_f32_array(f, 3), read_f32_array(f, 3)]

		f.seek(4, 1) # 4 bytes of padding

		stream = Vec_pointer(f)

		common_header["frame_count"] = frame_count
		common_header["scale_stream_quantization"] = scale_stream_quantization
		common_header["translation_stream_quantization"] = translation_stream_quantization
		common_header["stream_pointer"] = stream
	else:
		print(f"Read animated header // Error: Animated data codec is not type 0, 1 or 2, it is: {common_header["codec_type"]}!")
		return None

	return common_header

def parse_animated_codec_0(file_desc, animation_header, animated_bones_header, control_maps, bone_data):
	print("Parsing animated data // Info: Codec 0")

	animated_scale_control_map = control_maps["animated_scale_control_map"]
	animated_rotation_control_map = control_maps["animated_rotation_control_map"]
	animated_translation_control_map = control_maps["animated_translation_control_map"]

	animated_scale_stream = Tag_array(file_desc, animated_bones_header["scale_stream"], read_vec4)
	animated_rotation_stream = Tag_array(file_desc, animated_bones_header["rotation_stream"], read_vec4)
	animated_translation_stream = Tag_array(file_desc, animated_bones_header["translation_stream"], read_vec4)

	animation_duration_in_frames = animation_header["frame_count"]

	# animated
	for bone_map_i in range(animated_scale_control_map.length):
		bone_skeleton_i = animated_scale_control_map.read(bone_map_i)
		for frame_i in range(animation_duration_in_frames):
			scale = animated_scale_stream.read(bone_map_i * animation_duration_in_frames + frame_i)
			bone_data[bone_skeleton_i]["scales"].append(scale)

	for bone_map_i in range(animated_rotation_control_map.length):
		bone_skeleton_i = animated_rotation_control_map.read(bone_map_i)
		for frame_i in range(animation_duration_in_frames):
			rotation = animated_rotation_stream.read(bone_map_i * animation_duration_in_frames + frame_i)
			bone_data[bone_skeleton_i]["rotations"].append(rotation)

	for bone_map_i in range(animated_translation_control_map.length):
		bone_skeleton_i = animated_translation_control_map.read(bone_map_i)
		for frame_i in range(animation_duration_in_frames):
			translation = animated_translation_stream.read(bone_map_i * animation_duration_in_frames + frame_i)
			bone_data[bone_skeleton_i]["translations"].append(translation)

	return True

def parse_animated_codec_1(file_desc, animation_header, animated_bones_header, control_maps, bone_data):
	print("Parsing animated data // Info: Codec 1")

	uncompressed_data = Tag_array(file_desc, animated_bones_header["uncompressed_data"], read_u16)
	compressed_data = Tag_array(file_desc, animated_bones_header["compressed_data"], read_u16)
	keyframe_deltas = Tag_array(file_desc, animated_bones_header["keyframe_deltas"], read_u8)
	interpolation_data = Tag_array(file_desc, animated_bones_header["interpolation_data"], read_u8)
	quantization_minimums = Tag_array(file_desc, animated_bones_header["quantization_minimums"], read_f32)
	quantization_extents = Tag_array(file_desc, animated_bones_header["quantization_extents"], read_f32)
	array_7 = Tag_array(file_desc, animated_bones_header["array_7"], read_u16)

	if control_maps["animated_scale_control_map"].length > 0:
		print("Parsing animated data // Error: Have animated scales, cannot handle") # I have not seen even one animation with compressed scales, so idk how data will look like
		return False

	if array_7.read(-1) != compressed_data.length:
		print("Parsing animated data // Error: Array 7 last element not equals to compressed_data.length")
		return False

	animated_scale_control_map = control_maps["animated_scale_control_map"]
	animated_rotation_control_map = control_maps["animated_rotation_control_map"]
	animated_translation_control_map = control_maps["animated_translation_control_map"]

	animation_duration_in_frames = animation_header["frame_count"]

	# animated
	array_7_offset = 0

	# skipping animated scales as there is no example of how to work with them, so I cannot implement it yet

	for bone_map_i in range(animated_rotation_control_map.length):
		bone_skeleton_i = animated_rotation_control_map.read(bone_map_i)

		array_7_element = u16_to_s16(array_7.read(array_7_offset))

		track = []

		if array_7_element > 0: # compressed_data
			#print(f"bone {bone_skeleton_i} has compressed rotation")
			offset = array_7_element - 1 # because data is 1-indexed

			stride, offset = compressed_data.read_vec(offset, 3) # 3 flags
			frames_deltas_offset, interp_data_offset, frames_deltas_count = stride

			first_quat_components, offset = compressed_data.read_vec(offset, COMP_ROTATION_COMPONENTS)

			first_quat = decompress_quaternion(first_quat_components)
			# add left boundary, as further only interpolated data and right boundaries will be added
			track.append(first_quat)

			for i in range(frames_deltas_count):
				components, offset = compressed_data.read_vec(offset, COMP_ROTATION_COMPONENTS)
				second_quat = decompress_quaternion(components)

				frames = keyframe_deltas.read(frames_deltas_offset + i)
				interp_bytes, interp_data_offset = interpolation_data.read_vec(interp_data_offset, ROTATION_COMPONENTS)

				t0 = [calculate_tangent(interp_bytes[j], first_quat[j], second_quat[j], upper=True) for j in range(ROTATION_COMPONENTS)]
				t1 = [calculate_tangent(interp_bytes[j], first_quat[j], second_quat[j], upper=False) for j in range(ROTATION_COMPONENTS)]

				for f in range(1, frames): # until frames - 1
					t = f / frames
					x = hermite(first_quat[0], second_quat[0], t0[0], t1[0], t)
					y = hermite(first_quat[1], second_quat[1], t0[1], t1[1], t)
					z = hermite(first_quat[2], second_quat[2], t0[2], t1[2], t)
					w = hermite(first_quat[3], second_quat[3], t0[3], t1[3], t)

					track.append([x, y, z, w])

				# add right boundary and save it as left
				track.append(second_quat)
				first_quat = second_quat

		else: # uncompressed data
			#print(f"bone {bone_skeleton_i} has non-compressed rotation")
			offset = abs(array_7_element) - 1
			for i in range(animation_duration_in_frames):
				components, offset = uncompressed_data.read_vec(offset, COMP_ROTATION_COMPONENTS)

				quat = decompress_quaternion(components)
				track.append(quat)

		bone_data[bone_skeleton_i]["rotations"] = track
		array_7_offset += 1

	for bone_map_i in range(animated_translation_control_map.length):
		bone_skeleton_i = animated_translation_control_map.read(bone_map_i)

		array_7_element = u16_to_s16(array_7.read(array_7_offset))

		quantization_minimum = quantization_minimums.read(bone_map_i)
		quantization_extent = quantization_extents.read(bone_map_i)

		track = []

		if array_7_element > 0: # compressed_data
			#print(f"bone {bone_skeleton_i} has compressed translation")
			offset = array_7_element - 1 # because data is 1-indexed
			stride, offset = compressed_data.read_vec(offset, 3) # 3 flags
			frames_deltas_offset, interp_data_offset, frames_deltas_count = stride

			first_tr_components, offset = compressed_data.read_vec(offset, TRANSLATION_COMPONENTS)

			first_tr = [
				correct_quantization(
					decode_snorm16(x),
					quantization_minimum,
					quantization_extent
				) for x in first_tr_components
			]

			# add left boundary, as further only interpolated data and right boundaries will be added
			track.append(first_tr)

			for i in range(frames_deltas_count):
				components, offset = compressed_data.read_vec(offset, TRANSLATION_COMPONENTS)

				second_tr = [
					correct_quantization(
						decode_snorm16(x),
						quantization_minimum,
						quantization_extent
					) for x in components
				]

				frames = keyframe_deltas.read(frames_deltas_offset + i)
				interp_bytes, interp_data_offset = interpolation_data.read_vec(interp_data_offset, TRANSLATION_COMPONENTS)

				t0 = [calculate_tangent(interp_bytes[j], first_tr[j], second_tr[j], upper=True) for j in range(TRANSLATION_COMPONENTS)]
				t1 = [calculate_tangent(interp_bytes[j], first_tr[j], second_tr[j], upper=False) for j in range(TRANSLATION_COMPONENTS)]

				for f in range(1, frames):
					t = f / frames
					x = hermite(first_tr[0], second_tr[0], t0[0], t1[0], t)
					y = hermite(first_tr[1], second_tr[1], t0[1], t1[1], t)
					z = hermite(first_tr[2], second_tr[2], t0[2], t1[2], t)

					track.append([x, y, z])
				track.append(second_tr)

				first_tr = second_tr

		else: # uncompressed data
			#print(f"bone {bone_skeleton_i} has non-compressed translation")
			offset = abs(array_7_element) - 1
			for i in range(animation_duration_in_frames):
				components, offset = uncompressed_data.read_vec(offset, TRANSLATION_COMPONENTS)
				# these seems to be right
				tr = [
					correct_quantization( # apply quantization
						decode_snorm16(x),
						quantization_minimum,
						quantization_extent
					) for x in components
				]

				track.append(tr)

		bone_data[bone_skeleton_i]["translations"] = track

		array_7_offset += 1

	return True

def parse_animated_codec_2(file_desc, animation_header, animated_bones_header, control_maps, bone_data):
	print("Parsing animated data // Info: Codec 2")

	stream_data = Tag_array(file_desc, animated_bones_header["stream_data"], read_u16)
	quantization_minimums = Tag_array(file_desc, animated_bones_header["quantization_minimums"], read_f32)
	quantization_extents = Tag_array(file_desc, animated_bones_header["quantization_extents"], read_f32)

	animated_scale_control_map = control_maps["animated_scale_control_map"]
	animated_rotation_control_map = control_maps["animated_rotation_control_map"]
	animated_translation_control_map = control_maps["animated_translation_control_map"]

	animation_duration_in_frames = animation_header["frame_count"]

	# animated data
	stream_offset = 0 # offset in common stream
	quantization_offset = 0 # offset in quantization streams

	for bone_map_i in range(animated_scale_control_map.length):
		bone_skeleton_i = animated_scale_control_map.read(bone_map_i)

		for frame_i in range(animation_duration_in_frames):
			scale = correct_quantization(
				unpack_unorm16(
					stream_data.read(stream_offset)
				),
				quantization_minimums.read(quantization_offset),
				quantization_extents.read(quantization_offset)
			)

			bone_data[bone_skeleton_i]["scales"].append(scale)
			stream_offset += SCALE_COMPONENTS

		quantization_offset += SCALE_COMPONENTS

	for bone_map_i in range(animated_rotation_control_map.length):
		bone_skeleton_i = animated_rotation_control_map.read(bone_map_i)

		for frame_i in range(animation_duration_in_frames):
			rotation = [
				correct_quantization(
					unpack_unorm16(
						stream_data.read(stream_offset + component_i)
					),
					quantization_minimums.read(quantization_offset + component_i),
					quantization_extents.read(quantization_offset + component_i)
				) for component_i in range(ROTATION_COMPONENTS)
			]

			bone_data[bone_skeleton_i]["rotations"].append(rotation)
			stream_offset += ROTATION_COMPONENTS

		quantization_offset += ROTATION_COMPONENTS

	for bone_map_i in range(animated_translation_control_map.length):
		bone_skeleton_i = animated_translation_control_map.read(bone_map_i)

		for frame_i in range(animation_duration_in_frames):
			translation = [
				correct_quantization(
					unpack_unorm16(
						stream_data.read(stream_offset + component_i)
					),
					quantization_minimums.read(quantization_offset + component_i),
					quantization_extents.read(quantization_offset + component_i)
				) for component_i in range(TRANSLATION_COMPONENTS)
			]

			bone_data[bone_skeleton_i]["translations"].append(translation)
			stream_offset += TRANSLATION_COMPONENTS

		quantization_offset += TRANSLATION_COMPONENTS
	return True

def add_static_bones(file_desc, animation_header, static_bones_header, control_maps, bone_data):
	static_scale_control_map = control_maps["static_scale_control_map"]
	static_rotation_control_map = control_maps["static_rotation_control_map"]
	static_translation_control_map = control_maps["static_translation_control_map"]

	animation_duration_in_frames = animation_header["frame_count"]
	static_streams = parse_static_bones_stream(file_desc, animation_header, static_bones_header)

	static_scale_stream = static_streams["scale"]
	static_rotation_stream = static_streams["rotation"]
	static_translation_stream  = static_streams["translation"]

	for bone_map_i in range(static_scale_control_map.length):
		bone_skeleton_i = static_scale_control_map.read(bone_map_i)
		#for frame_i in range(animation_duration_in_frames):
		bone_data[bone_skeleton_i]["scales"].append(static_scale_stream[bone_map_i])

	for bone_map_i in range(static_rotation_control_map.length):
		bone_skeleton_i = static_rotation_control_map.read(bone_map_i)
		#for frame_i in range(animation_duration_in_frames):
		bone_data[bone_skeleton_i]["rotations"].append(static_rotation_stream[bone_map_i])

	for bone_map_i in range(static_translation_control_map.length):
		bone_skeleton_i = static_translation_control_map.read(bone_map_i)
		#for frame_i in range(animation_duration_in_frames):
		bone_data[bone_skeleton_i]["translations"].append(static_translation_stream[bone_map_i])

def add_animated_bones(file_desc, animation_header, animated_bones_header, control_maps, bone_data):
	check = False

	if animated_bones_header["codec_type"] == 0:
		check = parse_animated_codec_0(file_desc, animation_header, animated_bones_header, control_maps, bone_data)
	elif animated_bones_header["codec_type"] == 1:
		check = parse_animated_codec_1(file_desc, animation_header, animated_bones_header, control_maps, bone_data)
	elif animated_bones_header["codec_type"] == 2:
		check = parse_animated_codec_2(file_desc, animation_header, animated_bones_header, control_maps, bone_data)
	elif animated_bones_header["codec_type"] == 3:
		check = parse_animated_codec_3(file_desc, animation_header, animated_bones_header, control_maps, bone_data)

	return check

def parse(file_desc, animation_header, static_bones_header, animated_bones_header, control_maps):
	animation_rate = 30
	animation_duration_in_frames = animation_header["frame_count"]
	animation_duration_in_seconds = animation_duration_in_frames / animation_rate
	rig_control_count = animation_header["rig_control_count"]

	log_animation_data(animation_duration_in_frames, animation_duration_in_seconds)

	bone_data = {
		i: {
			"scales": [],
			"rotations": [],
			"translations": [],
		}
		for i in range(rig_control_count)
	}

	# read runtime rig components
	components = read_rig_components(file_desc, animation_header["rig_components_array_pointer"])
	log_runtime_rig_components(components)

	animation_data = {
		"frame_count": animation_duration_in_frames,
		"node_count": animation_header["node_count"],
		"rig_control_count": animation_header["rig_control_count"],
		"static_codec_type": static_bones_header["codec_type"],
		"animated_codec_type": animated_bones_header["codec_type"],
		"static_scale_control_map": control_maps["static_scale_control_map"].payload,
		"static_rotation_control_map": control_maps["static_rotation_control_map"].payload,
		"static_translation_control_map": control_maps["static_translation_control_map"].payload,
		"animated_scale_control_map": control_maps["animated_scale_control_map"].payload,
		"animated_rotation_control_map": control_maps["animated_rotation_control_map"].payload,
		"animated_translation_control_map": control_maps["animated_translation_control_map"].payload,
		"rig_components": components.payload
	}

	add_static_bones(file_desc, animation_header, static_bones_header, control_maps, bone_data)

	animated_bones_check = add_animated_bones(file_desc, animation_header, animated_bones_header, control_maps, bone_data)

	if not animated_bones_check:
		return None

	return {"animation_data": animation_data, "bone_data": bone_data}

def parse_animation_file(file_desc, game_version):
	# read general codec
	animation_header = read_animation_file_header(file_desc, 0, game_version)
	log_animation_header(animation_header)

	# parse control maps
	control_maps = parse_control_maps(file_desc, animation_header, game_version)

	# read static data header
	static_bones_header = read_static_bones_header(file_desc, animation_header["static_bone_data"])

	if static_bones_header is None:
		print("Parsing animation file // Error: Could not read static bones data!")
		sys.exit(3)

	log_static_bones_header(static_bones_header)

	# check whether codec is supported
	if static_bones_header["codec_type"] != 3:
		print(F"Parsing animation file // Error: Static codec {static_bones_header["codec_type"]} is not supported")
		sys.exit(4)

	# read animated data header
	animated_bones_header = read_animated_bones_header(file_desc, animation_header["animated_bone_data"])

	if animated_bones_header is None:
		print("Parsing animation file // Error: Could not read animated bones data!")
		sys.exit(2)

	log_animated_bones_header(animated_bones_header)

	# check whether codec is supported
	if animated_bones_header["codec_type"] > 3 or animated_bones_header["codec_type"] < 0:
		print(F"Parsing animation file // Error: Animated codec {animated_bones_header["codec_type"]} is not supported")
		sys.exit(4)

	# construct bone data
	animation = parse(file_desc, animation_header, static_bones_header, animated_bones_header, control_maps)
	return animation

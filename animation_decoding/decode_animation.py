import math
import numpy as np

from dataclasses import dataclass
from numpy.typing import NDArray

from tag.tag_array import Tag_Array
from tag_readers.read_animation import (
	Animation_Data, Animation_Header,
	Codec_0_Header, Codec_0_Buffers,
	Codec_1_Header, Codec_1_Buffers,
	Codec_2_Header, Codec_2_Buffers,
	Codec_3_Header, Codec_3_Buffers,
	Codec_Buffers_Union,
	Codec_Header_Union,
	Uncompressed_Tracks,
	Control_Maps,

)
from .animation_interpolation import hermite, calculate_tangent


SCALE_COMPONENTS = 1
ROTATION_COMPONENTS = 4
COMP_ROTATION_COMPONENTS = 3
TRANSLATION_COMPONENTS = 3


@dataclass(slots=True)
class Bone_Tracks:
	bone_name_hash: int = 0
	scales: NDArray[np.float32] | None = None  # (frame_count,)
	rotations: NDArray[np.float32] | None = None  # (frame_count, 4)
	translations: NDArray[np.float32] | None = None  # (frame_count, 3)


# NOTE: reading compressed binary quaternion data as float_s16 matches quaternion components from api
# it seems:
# 	float_s16[0] is quat.w
#	float_s16[1] is quat.x
#	float_s16[2] is quat.y
# so the missing component is always quat.z
# NOTE: How to get Z's sign?? Mathematically both z and -z are correct
# I assume components[1] lesser bit holds sign 1 for minus, 0 for plus,
# but need more statistics
# NOTE: Checked of all the data available so it seems to be working
# If it does not work this is just the worst coincidence possible
def decompress_quaternion_scalar(components: list[int]) -> list[float]:
	floats = [unpack_snorm16_scalar(x) for x in components]

	w, x, y = floats
	z = math.sqrt(max(1 - w * w - x * x - y * y, 0))

	if math.fabs(x * x + y * y + z * z + w * w - 1) > 0.001:
		raise Exception(f"quat norm is not close to 1: {x * x + y * y + z * z + w * w}")

	if components[1] & 1 == 1:
		z = -z

	return [x, y, z, w]


def decompress_quaternion_vector(components: np.ndarray) -> np.ndarray:
	"""
	take frame matrix, shape (N, 3), components [w, x, y].
	return matrix, shape (N, 4), components [x, y, z, w].
	"""
	floats = components.view(np.int16) / 32767.0  # decode_snorm16
	w = floats[..., 0]
	x = floats[..., 1]
	y = floats[..., 2]

	z_squared = 1.0 - w ** 2 - x ** 2 - y ** 2
	z = np.sqrt(np.maximum(z_squared, 0.0))

	sign_mask = (components[..., 1] & 1) == 1
	z = np.where(sign_mask, -z, z)

	return np.stack([x, y, z, w], axis=-1)


def unpack_unorm16_scalar(value: int) -> float:
	return value / 65535


def unpack_unorm16_vector(array: np.ndarray) -> np.ndarray:
	return array / 65535.0


def unpack_snorm16_scalar(value: int) -> float:
	return value / 32767.0


def decode_snorm16_vector(u16_array: np.ndarray) -> np.ndarray:
	return u16_array.view(np.int16) / 32767.0


def correct_quantization_scalar(value: float, minimum: float, extent: float) -> float:
	return value * minimum + extent


def correct_quantization_vector(
	value: np.ndarray,
	minimum: np.ndarray | float,
	extent: np.ndarray | float
) -> np.ndarray:
	return value * minimum + extent



def decode_codec_0_buffers(codec_header: Codec_0_Header, buffers: Codec_0_Buffers) -> Uncompressed_Tracks:
	frame_count = codec_header.frame_count

	scales = buffers.animated_scale_stream.data.reshape(codec_header.scale_stream_count, frame_count)
	rotations = buffers.animated_rotation_stream.data.reshape(codec_header.rotation_stream_count, frame_count, 4)
	translations = buffers.animated_translation_stream.data.reshape(codec_header.translation_stream_count, frame_count, 4)

	return Uncompressed_Tracks(scales, rotations, translations)


def decode_codec_1_buffers(codec_header: Codec_1_Header, buffers: Codec_1_Buffers, expected_frame_count: int) -> Uncompressed_Tracks:
	uncompressed_data = buffers.uncompressed_data
	compressed_data = buffers.compressed_data
	keyframe_deltas = buffers.keyframe_deltas
	interpolation_data = buffers.interpolation_data
	quantization_minimums = buffers.quantization_minimums
	quantization_extents = buffers.quantization_extents
	array_7 = buffers.array_7

	if array_7[-1] != compressed_data.length:
		raise Exception("Parsing codec data // Error: Array 7 last element not equals to compressed_data.length")

	frame_count = expected_frame_count

	# allocate all the data at once
	# shape (bones_count, frames_count, 1 component (so 2D array))
	scales = np.empty((codec_header.scale_stream_count, frame_count), dtype=np.float32)
	# shape (bones_count, frames_count, 4 components)
	rotations = np.empty((codec_header.rotation_stream_count, frame_count, 4), dtype=np.float32)
	# shape (bones_count, frames_count, 3 components)
	translations = np.empty((codec_header.translation_stream_count, frame_count, 3), dtype=np.float32)

	# animated
	array_7_offset = 0

	for bone_map_i in range(codec_header.scale_stream_count):
		array_7_element = array_7[array_7_offset]

		if array_7_element > 0:  # compressed_data
			offset = array_7_element - 1  # because data is 1-indexed
			stride, offset = compressed_data.read_vec(offset, 3)
			frames_deltas_offset, interp_data_offset, frames_deltas_count = stride

			raw_sc, offset = compressed_data.read_scalar(offset) # scalar adds one, so no need to use SCALE_COMPONENTS
			first_sc = unpack_snorm16_scalar(raw_sc)

			deltas = keyframe_deltas.data[frames_deltas_offset: frames_deltas_offset + frames_deltas_count]

			scales[bone_map_i, 0] = first_sc

			insert_start_index = 1
			for i in range(frames_deltas_count):
				raw_sc, offset = compressed_data.read_scalar(offset)
				second_sc = unpack_snorm16_scalar(raw_sc)

				frames_delta = np.int32(deltas[i])
				interp_byte, interp_data_offset = interpolation_data.read_scalar(interp_data_offset)

				t0 = calculate_tangent(interp_byte, first_sc, second_sc, upper=True)
				t1 = calculate_tangent(interp_byte, first_sc, second_sc, upper=False)
				# generate timeline
				t_array = np.arange(1, frames_delta + 1, dtype=np.float32) / frames_delta
				# interpolate
				scales[
					bone_map_i,
					insert_start_index: insert_start_index + frames_delta
				] = hermite(first_sc, second_sc, t0, t1, t_array)

				insert_start_index += frames_delta
				first_sc = second_sc  # second becomes first

		else:  # uncompressed data
			offset = abs(array_7_element) - 1
			scales[bone_map_i] = decode_snorm16_vector(uncompressed_data.data[offset: offset + frame_count])

		array_7_offset += 1

	for bone_map_i in range(codec_header.rotation_stream_count):
		array_7_element = array_7[array_7_offset]

		if array_7_element > 0:  # compressed_data
			offset = array_7_element - 1  # because data is 1-indexed
			stride, offset = compressed_data.read_vec(offset, 3)  # 3 flags
			frames_deltas_offset, interp_data_offset, frames_deltas_count = stride

			raw_quat, offset = compressed_data.read_vec(offset, COMP_ROTATION_COMPONENTS)
			first_quat = np.array(decompress_quaternion_scalar(raw_quat.tolist()))

			deltas = keyframe_deltas.data[frames_deltas_offset: frames_deltas_offset + frames_deltas_count]
			rotations[bone_map_i, 0] = first_quat

			insert_start_index = 1
			for i in range(frames_deltas_count):
				raw_quat, offset = compressed_data.read_vec(offset, COMP_ROTATION_COMPONENTS)
				second_quat = np.array(decompress_quaternion_scalar(raw_quat.tolist()))

				frames_delta = np.int32(deltas[i])
				interp_bytes, interp_data_offset = interpolation_data.read_vec(interp_data_offset, ROTATION_COMPONENTS)

				t0 = [calculate_tangent(interp_bytes[j], first_quat[j], second_quat[j], upper=True) for j in range(ROTATION_COMPONENTS)]
				t1 = [calculate_tangent(interp_bytes[j], first_quat[j], second_quat[j], upper=False) for j in range(ROTATION_COMPONENTS)]
				# generate timeline
				t_array = (np.arange(1, frames_delta + 1, dtype=np.float32) / frames_delta)[:, np.newaxis]
				# interpolate
				rotations[
					bone_map_i,
					insert_start_index: insert_start_index + frames_delta
				] = hermite(first_quat, second_quat, t0, t1, t_array)

				insert_start_index += frames_delta
				first_quat = second_quat

		else:  # uncompressed data
			offset = abs(array_7_element) - 1

			chunk, offset = uncompressed_data.read_vec(offset, frame_count * COMP_ROTATION_COMPONENTS)
			rotations[bone_map_i] = decompress_quaternion_vector(chunk.reshape(frame_count, COMP_ROTATION_COMPONENTS))

		array_7_offset += 1

	for bone_map_i in range(codec_header.translation_stream_count):
		array_7_element = array_7[array_7_offset]

		quantization_minimum = quantization_minimums[bone_map_i]
		quantization_extent = quantization_extents[bone_map_i]

		if array_7_element > 0:  # compressed_data
			offset = array_7_element - 1  # because data is 1-indexed
			stride, offset = compressed_data.read_vec(offset, 3)  # 3 flags
			frames_deltas_offset, interp_data_offset, frames_deltas_count = stride

			raw_tr, offset = compressed_data.read_vec(offset, TRANSLATION_COMPONENTS)
			first_tr = np.array(
				[
					correct_quantization_scalar(
						unpack_snorm16_scalar(x),
						quantization_minimum,
						quantization_extent
					)
					for x in raw_tr
				]
			)

			deltas = keyframe_deltas.data[frames_deltas_offset: frames_deltas_offset + frames_deltas_count]
			# add left boundary, as further only interpolated data and right boundaries will be added
			translations[bone_map_i, 0] = first_tr

			insert_start_index = 1
			for i in range(frames_deltas_count):
				raw_tr, offset = compressed_data.read_vec(offset, TRANSLATION_COMPONENTS)

				second_tr = np.array(
					[
						correct_quantization_scalar(
							unpack_snorm16_scalar(x),
							quantization_minimum,
							quantization_extent
						)
						for x in raw_tr
					]
				)

				frames_delta = np.int32(deltas[i])
				interp_bytes, interp_data_offset = interpolation_data.read_vec(interp_data_offset, TRANSLATION_COMPONENTS)

				t0 = [calculate_tangent(interp_bytes[j], first_tr[j], second_tr[j], upper=True) for j in range(TRANSLATION_COMPONENTS)]
				t1 = [calculate_tangent(interp_bytes[j], first_tr[j], second_tr[j], upper=False) for j in range(TRANSLATION_COMPONENTS)]
				# generate timeline
				t_array = (np.arange(1, frames_delta + 1, dtype=np.float32) / frames_delta)[:, np.newaxis]
				# interpolate
				translations[
					bone_map_i,
					insert_start_index: insert_start_index + frames_delta
				] = hermite(first_tr, second_tr, t0, t1, t_array)

				insert_start_index += frames_delta
				first_tr = second_tr

		else:  # uncompressed data
			offset = abs(array_7_element) - 1
			chunk, offset = uncompressed_data.read_vec(offset, frame_count * TRANSLATION_COMPONENTS)
			translations[bone_map_i] = correct_quantization_vector(
				decode_snorm16_vector(chunk.reshape(frame_count, TRANSLATION_COMPONENTS)), quantization_minimum,
				quantization_extent
			)

		array_7_offset += 1

	return Uncompressed_Tracks(scales, rotations, translations)


def decode_codec_2_buffers(codec_header: Codec_2_Header, buffers: Codec_2_Buffers) -> Uncompressed_Tracks:
	frame_count = codec_header.frame_count
	stream_data = buffers.stream_data
	quantization_minimums = buffers.quantization_minimums
	quantization_extents = buffers.quantization_extents

	sc_size = codec_header.scale_stream_count * frame_count * SCALE_COMPONENTS
	rot_size = codec_header.rotation_stream_count * frame_count * ROTATION_COMPONENTS
	tr_size = codec_header.translation_stream_count * frame_count * TRANSLATION_COMPONENTS

	sc_end = sc_size
	rot_end = sc_end + rot_size
	tr_end = rot_end + tr_size

	# (bones_count, frames, 1)
	raw_scales = stream_data.data[0: sc_end].reshape(codec_header.scale_stream_count, frame_count)
	# rotations: (bones_count, frames, 4 components [x, y, z, w])
	raw_rotations = stream_data.data[sc_end: rot_end].reshape(codec_header.rotation_stream_count, frame_count, 4)
	# translations: (bones_count, frames, 3 components [x, y, z])
	raw_translations = stream_data.data[rot_end: tr_end].reshape(codec_header.translation_stream_count, frame_count, 3)

	sc_quant_end = codec_header.scale_stream_count * SCALE_COMPONENTS
	rot_quat_end = sc_quant_end + codec_header.rotation_stream_count * ROTATION_COMPONENTS
	tr_quant_end = rot_quat_end + codec_header.translation_stream_count * TRANSLATION_COMPONENTS

	# 1 component for each bone across all frames (bones_count, 1)
	sc_quant_mins = quantization_minimums.data[0: sc_quant_end].reshape(codec_header.scale_stream_count, 1)
	sc_quant_exts = quantization_extents.data[0: sc_quant_end].reshape(codec_header.scale_stream_count, 1)
	# 4 components for each bone across all frames (bones_count, 4)
	rot_quant_mins = quantization_minimums.data[sc_quant_end: rot_quat_end].reshape(codec_header.rotation_stream_count, 4)
	rot_quant_exts = quantization_extents.data[sc_quant_end: rot_quat_end].reshape(codec_header.rotation_stream_count, 4)
	# 3 components for each bone across all frames (bones_count, 3)
	tr_quant_mins = quantization_minimums.data[rot_quat_end: tr_quant_end].reshape(codec_header.translation_stream_count, 3)
	tr_quant_exts = quantization_extents.data[rot_quat_end: tr_quant_end].reshape(codec_header.translation_stream_count, 3)

	scales = correct_quantization_vector(
		unpack_unorm16_vector(raw_scales),
		sc_quant_mins,
		sc_quant_exts
	)

	rotations = correct_quantization_vector(
		unpack_unorm16_vector(raw_rotations),
		rot_quant_mins[:, np.newaxis, :],
		rot_quant_exts[:, np.newaxis, :]
	)

	translations = correct_quantization_vector(
		unpack_unorm16_vector(raw_translations),
		tr_quant_mins[:, np.newaxis, :],
		tr_quant_exts[:, np.newaxis, :]
	)

	return Uncompressed_Tracks(scales, rotations, translations)


def decode_codec_3_buffers(codec_header: Codec_3_Header, buffers: Codec_3_Buffers) -> Uncompressed_Tracks:
	frame_count = codec_header.frame_count
	stream_data = buffers.stream_data

	scale_min, scale_extent = codec_header.scale_stream_quantization

	tr_min = np.array(codec_header.translation_stream_quantization[0], dtype=np.float32)
	tr_extent = np.array(codec_header.translation_stream_quantization[1], dtype=np.float32)

	sc_size = codec_header.scale_stream_count * frame_count * SCALE_COMPONENTS
	rot_size = codec_header.rotation_stream_count * frame_count * ROTATION_COMPONENTS
	tr_size = codec_header.translation_stream_count * frame_count * TRANSLATION_COMPONENTS

	sc_end = sc_size
	rot_end = sc_end + rot_size
	tr_end = rot_end + tr_size

	# (bones_count, frames)
	raw_scales = stream_data.data[0: sc_end].reshape(codec_header.scale_stream_count, frame_count)

	# rotations: (bones_count, frames, 4 components [x, y, z, w])
	raw_rotations = stream_data.data[sc_end: rot_end].reshape(codec_header.rotation_stream_count, frame_count, 4)

	# translations: (bones_count, frames, 3 components [x, y, z])
	raw_translations = stream_data.data[rot_end: tr_end].reshape(codec_header.translation_stream_count, frame_count, 3)

	# all scales have same min and extent
	scales = correct_quantization_vector(unpack_unorm16_vector(raw_scales), scale_min, scale_extent)
	# rotations' min and ext are 2, -1
	rotations = correct_quantization_vector(unpack_unorm16_vector(raw_rotations), 2.0, -1.0)
	# translations' min and ext are also the same but are per-component
	translations = correct_quantization_vector(unpack_unorm16_vector(raw_translations), tr_min, tr_extent)

	return Uncompressed_Tracks(scales, rotations, translations)


def decode_codec_buffers(
	animation_header: Animation_Header,
	codec_header: Codec_Header_Union | None,
	buffers: Codec_Buffers_Union | None
) -> Uncompressed_Tracks | None:
	if codec_header is None or buffers is None:
		return None

	if isinstance(buffers, Codec_0_Buffers) and isinstance(codec_header, Codec_0_Header):
		return decode_codec_0_buffers(codec_header, buffers)
	elif isinstance(buffers, Codec_1_Buffers) and isinstance(codec_header, Codec_1_Header):
		return decode_codec_1_buffers(codec_header, buffers, animation_header.frame_count)
	elif isinstance(buffers, Codec_2_Buffers) and isinstance(codec_header, Codec_2_Header):
		return decode_codec_2_buffers(codec_header, buffers)
	elif isinstance(buffers, Codec_3_Buffers) and isinstance(codec_header, Codec_3_Header):
		return decode_codec_3_buffers(codec_header, buffers)
	else:
		return None


def assign_tracks(
		bone_data: list[Bone_Tracks],
		uncompressed_tracks: Uncompressed_Tracks,
		scale_control_map: Tag_Array,
		rotation_control_map: Tag_Array,
		translation_control_map: Tag_Array
):
	for bone_map_i, bone_skeleton_i in enumerate(scale_control_map):
		bone_data[bone_skeleton_i].scales = uncompressed_tracks.scales[bone_map_i]

	for bone_map_i, bone_skeleton_i in enumerate(rotation_control_map):
		bone_data[bone_skeleton_i].rotations = uncompressed_tracks.rotations[bone_map_i]

	for bone_map_i, bone_skeleton_i in enumerate(translation_control_map):
		bone_data[bone_skeleton_i].translations = uncompressed_tracks.translations[bone_map_i]


def add_static_bones_data(
	animation_header: Animation_Header,
	static_bones_header: Codec_Header_Union | None,
	static_bones_buffers: Codec_Buffers_Union | None,
	control_maps: Control_Maps,
	bone_data: list[Bone_Tracks]
):
	uncompressed_tracks = decode_codec_buffers(animation_header, static_bones_header, static_bones_buffers)  # static data *should* have only one frame

	if uncompressed_tracks is None:
		return

	assign_tracks(
		bone_data,
		uncompressed_tracks,
		control_maps.static_scale_control_map,
		control_maps.static_rotation_control_map,
		control_maps.static_translation_control_map
	)


def add_animated_bones_data(
	animation_header: Animation_Header,
	animated_bones_header: Codec_Header_Union,
	animated_bones_buffers: Codec_Buffers_Union,
	control_maps: Control_Maps,
	bone_data: list[Bone_Tracks]
):
	uncompressed_tracks = decode_codec_buffers(animation_header, animated_bones_header, animated_bones_buffers)  # animated data *should* as many frames as in general header

	if uncompressed_tracks is None:
		return

	assign_tracks(
		bone_data,
		uncompressed_tracks,
		control_maps.animated_scale_control_map,
		control_maps.animated_rotation_control_map,
		control_maps.animated_translation_control_map
	)


def decode_animation(animation_data: Animation_Data) -> list[Bone_Tracks]:
	animation_header = animation_data.animation_header
	rig_control_count = animation_header.rig_control_count
	static_bones_header = animation_data.static_bones_header
	static_bones_buffers = animation_data.static_bones_buffers
	animated_bones_header = animation_data.animated_bones_header
	animated_bones_buffers = animation_data.animated_bones_buffers
	control_maps = animation_data.control_maps

	bone_data = [Bone_Tracks() for _ in range(rig_control_count)]

	if static_bones_header is not None:
		add_static_bones_data(animation_header, static_bones_header, static_bones_buffers, control_maps, bone_data)

	if animated_bones_header is not None:
		add_animated_bones_data(animation_header, animated_bones_header, animated_bones_buffers, control_maps, bone_data)

	return bone_data

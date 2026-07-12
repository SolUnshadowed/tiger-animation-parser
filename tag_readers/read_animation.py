import logging
import sys
import numpy as np

from numpy.typing import NDArray
from typing import BinaryIO, Callable
from dataclasses import dataclass

from tag.tag_array import Tag_Array, Tag_Array_NP
from tag.tag_pointers import Base_Tag_Pointer, Rel_Pointer, Vec_Pointer
from tag.game_version import Game_Version
from tag.type_read_functions import read_u8, read_u16, read_u32, read_u64, read_rig_component, read_f32, read_f32_array
from tag.endianness import get_game_endianness, Endianness
from tag.data_structures import Rig_Component


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Animation_Header:
	file_size: int
	static_bone_data_pointer: Rel_Pointer
	animated_bone_data_pointer: Rel_Pointer
	extra_data_0_pointer: Rel_Pointer
	extra_data_1_pointer: Rel_Pointer  # some animation like codec header but with shortened error/stream lengths block?
	extra_data_2_pointer: Rel_Pointer  # array pointer, array of some structs (structs can have grip and support string hashes in)
	extra_data_3_pointer: Rel_Pointer  # animation codec? But it seems it has polymorphic header or it is normal for any codec?
	extra_data_4_pointer: Rel_Pointer  # animation codec?
	extra_data_5_pointer: Rel_Pointer  # two array pointer, first of floats second of u32? something quantized?
	extra_data_6_pointer: Rel_Pointer
	extra_data_7_pointer: Rel_Pointer
	static_scale_control_map_pointer: Vec_Pointer
	static_rotation_control_map_pointer: Vec_Pointer
	static_translation_control_map_pointer: Vec_Pointer
	animated_scale_control_map_pointer: Vec_Pointer
	animated_rotation_control_map_pointer: Vec_Pointer
	animated_translation_control_map_pointer: Vec_Pointer
	animation_hash: int
	frame_count: int
	node_count: int
	rig_control_count: int
	frame_events_array_pointer: Vec_Pointer
	rig_components_array_pointer: Vec_Pointer


@dataclass(slots=True)
class Base_Animation_Codec_Header:
	codec_type: int
	scale_stream_count: int
	rotation_stream_count: int
	translation_stream_count: int
	prob_error_value: float
	prob_compression_rate: float


@dataclass(slots=True)
class Codec_0_Header(Base_Animation_Codec_Header):
	frame_count: int
	scale_stream_pointer: Vec_Pointer
	rotation_stream_pointer: Vec_Pointer
	translation_stream_pointer: Vec_Pointer


@dataclass(slots=True)
class Codec_1_Header(Base_Animation_Codec_Header):
	uncompressed_data_pointer: Vec_Pointer
	compressed_data_pointer: Vec_Pointer
	keyframe_deltas_pointer: Vec_Pointer
	interpolation_data_pointer: Vec_Pointer
	quantization_minimums_pointer: Vec_Pointer
	quantization_extents_pointer: Vec_Pointer
	array_7_pointer: Vec_Pointer


@dataclass(slots=True)
class Codec_2_Header(Base_Animation_Codec_Header):
	frame_count: int
	stream_data_pointer: Vec_Pointer
	quantization_minimums_pointer: Vec_Pointer
	quantization_extents_pointer: Vec_Pointer


@dataclass(slots=True)
class Codec_3_Header(Base_Animation_Codec_Header):
	frame_count: int
	scale_stream_quantization: tuple[float, float]
	translation_stream_quantization: tuple[tuple[float, float, float], tuple[float, float, float]]
	stream_data_pointer: Vec_Pointer


type Codec_Header_Union = Codec_0_Header | Codec_1_Header | Codec_2_Header | Codec_3_Header


@dataclass(slots=True)
class Codec_0_Buffers:
	animated_scale_stream: Tag_Array_NP
	animated_rotation_stream: Tag_Array_NP
	animated_translation_stream: Tag_Array_NP


@dataclass(slots=True)
class Codec_1_Buffers:
	uncompressed_data: Tag_Array_NP
	compressed_data: Tag_Array_NP
	keyframe_deltas: Tag_Array_NP
	interpolation_data: Tag_Array_NP
	quantization_minimums: Tag_Array_NP
	quantization_extents: Tag_Array_NP
	array_7: Tag_Array_NP


@dataclass(slots=True)
class Codec_2_Buffers:
	stream_data: Tag_Array_NP
	quantization_minimums: Tag_Array_NP
	quantization_extents: Tag_Array_NP


@dataclass(slots=True)
class Codec_3_Buffers:
	stream_data: Tag_Array_NP


type Codec_Buffers_Union = Codec_0_Buffers | Codec_1_Buffers | Codec_2_Buffers | Codec_3_Buffers


@dataclass(slots=True)
class Uncompressed_Tracks:
	scales: NDArray[np.float32]
	rotations: NDArray[np.float32]
	translations: NDArray[np.float32]


@dataclass(slots=True)
class Control_Maps:
	static_scale_control_map: Tag_Array[int]
	static_rotation_control_map: Tag_Array[int]
	static_translation_control_map: Tag_Array[int]
	animated_scale_control_map: Tag_Array[int]
	animated_rotation_control_map: Tag_Array[int]
	animated_translation_control_map: Tag_Array[int]


@dataclass(slots=True)
class Animation_Data:
	animation_header: Animation_Header
	static_bones_header: Codec_Header_Union | None
	static_bones_buffers: Codec_Buffers_Union | None
	animated_bones_header: Codec_Header_Union | None
	animated_bones_buffers: Codec_Buffers_Union | None
	control_maps: Control_Maps
	runtime_rig_components: Tag_Array[Rig_Component]


def read_animation_header(f: BinaryIO, offset: int, game_version: Game_Version) -> Animation_Header:
	padding_0 = {Game_Version.D1_DEV_ALPHA: 12, Game_Version.D1_ROI: 8, Game_Version.D2_SK: 8, Game_Version.D2_EOF: 8, Game_Version.MARATHON: 8}
	padding_1 = {Game_Version.D1_DEV_ALPHA: 56, Game_Version.D1_ROI: 56, Game_Version.D2_SK: 72, Game_Version.D2_EOF: 72, Game_Version.MARATHON: 72}
	padding_2 = {Game_Version.D1_DEV_ALPHA: 24, Game_Version.D1_ROI: 24, Game_Version.D2_SK: 24, Game_Version.D2_EOF: 24, Game_Version.MARATHON: 24}
	padding_3 = {Game_Version.D1_DEV_ALPHA: 20, Game_Version.D1_ROI: 20, Game_Version.D2_SK: 24, Game_Version.D2_EOF: 28, Game_Version.MARATHON: 28}
	padding_4 = {Game_Version.D1_DEV_ALPHA: 12, Game_Version.D1_ROI: 4, Game_Version.D2_SK: 14, Game_Version.D2_EOF: 10, Game_Version.MARATHON: 10}

	f.seek(offset)
	endianness: Endianness = get_game_endianness(game_version)

	file_size = 0

	if game_version == Game_Version.D1_DEV_ALPHA:
		file_size = read_u32(f, endianness)
	else:
		file_size = read_u64(f, endianness)

	f.seek(padding_0[game_version], 1)  # 8 bytes of padding

	static_bone_data_pointer = Rel_Pointer(f, game_version)
	animated_bone_data_pointer = Rel_Pointer(f, game_version)
	extra_data_0 = Rel_Pointer(f, game_version)
	extra_data_1 = Rel_Pointer(f, game_version)
	extra_data_2 = Rel_Pointer(f, game_version)
	extra_data_3 = Rel_Pointer(f, game_version)
	extra_data_4 = Rel_Pointer(f, game_version)
	extra_data_5 = Rel_Pointer(f, game_version)
	extra_data_6 = Rel_Pointer(f, game_version)
	extra_data_7 = Rel_Pointer(f, game_version)

	f.seek(padding_1[game_version], 1)

	static_scale_control_map_pointer = Vec_Pointer(f, game_version)
	static_rotation_control_map_pointer = Vec_Pointer(f, game_version)
	static_translation_control_map_pointer = Vec_Pointer(f, game_version)
	animated_scale_control_map_pointer = Vec_Pointer(f, game_version)
	animated_rotation_control_map_pointer = Vec_Pointer(f, game_version)
	animated_translation_control_map_pointer = Vec_Pointer(f, game_version)

	f.seek(padding_2[game_version], 1)

	animation_hash = read_u32(f, endianness)

	f.seek(padding_3[game_version], 1)

	frame_count = read_u16(f, endianness)
	node_count = 0

	if game_version == Game_Version.D1_DEV_ALPHA or game_version == Game_Version.D1_ROI:
		node_count = read_u8(f, endianness)
	else:
		node_count = read_u16(f, endianness)

	rig_control_count = 0

	if game_version == Game_Version.D1_DEV_ALPHA or game_version == Game_Version.D1_ROI:
		rig_control_count = read_u8(f, endianness)
	else:
		rig_control_count = read_u16(f, endianness)

	f.seek(padding_4[game_version], 1)

	unk_arr_1_pointer = Vec_Pointer(f, game_version)

	# points to an array of rel pointers
	# each pointer points to frame event in the file
	frame_events_array_pointer = Vec_Pointer(f, game_version)
	rig_components_array_pointer = Vec_Pointer(f, game_version)

	return Animation_Header(
		file_size=file_size,
		static_bone_data_pointer=static_bone_data_pointer,
		animated_bone_data_pointer=animated_bone_data_pointer,
		extra_data_0_pointer=extra_data_0,
		extra_data_1_pointer=extra_data_1,
		extra_data_2_pointer=extra_data_2,
		extra_data_3_pointer=extra_data_3,
		extra_data_4_pointer=extra_data_4,
		extra_data_5_pointer=extra_data_5,
		extra_data_6_pointer=extra_data_6,
		extra_data_7_pointer=extra_data_7,
		static_scale_control_map_pointer=static_scale_control_map_pointer,
		static_rotation_control_map_pointer=static_rotation_control_map_pointer,
		static_translation_control_map_pointer=static_translation_control_map_pointer,
		animated_scale_control_map_pointer=animated_scale_control_map_pointer,
		animated_rotation_control_map_pointer=animated_rotation_control_map_pointer,
		animated_translation_control_map_pointer=animated_translation_control_map_pointer,
		animation_hash=animation_hash,
		frame_count=frame_count,
		node_count=node_count,
		rig_control_count=rig_control_count,
		frame_events_array_pointer=frame_events_array_pointer,
		rig_components_array_pointer=rig_components_array_pointer,
	)


def read_control_maps(f: BinaryIO, animation_header: Animation_Header, game_version: Game_Version) -> Control_Maps:
	functions: dict[Game_Version, Callable[[BinaryIO, Endianness], int]] = {
		Game_Version.D1_DEV_ALPHA: read_u8,
		Game_Version.D1_ROI: read_u8,
		Game_Version.D2_SK: read_u16,
		Game_Version.D2_EOF: read_u16,
		Game_Version.MARATHON: read_u16
	}
	# static
	static_scale_control_map = Tag_Array(f, animation_header.static_scale_control_map_pointer, functions[game_version])
	static_rotation_control_map = Tag_Array(f, animation_header.static_rotation_control_map_pointer, functions[game_version])
	static_translation_control_map = Tag_Array(f, animation_header.static_translation_control_map_pointer, functions[game_version])
	# animated
	animated_scale_control_map = Tag_Array(f, animation_header.animated_scale_control_map_pointer, functions[game_version])
	animated_rotation_control_map = Tag_Array(f, animation_header.animated_rotation_control_map_pointer, functions[game_version])
	animated_translation_control_map = Tag_Array(f, animation_header.animated_translation_control_map_pointer, functions[game_version])

	return Control_Maps(
		static_scale_control_map=static_scale_control_map,
		static_rotation_control_map=static_rotation_control_map,
		static_translation_control_map=static_translation_control_map,
		animated_scale_control_map=animated_scale_control_map,
		animated_rotation_control_map=animated_rotation_control_map,
		animated_translation_control_map=animated_translation_control_map
	)


# version independent
def read_common_codec_header(f: BinaryIO, game_version: Game_Version) -> Base_Animation_Codec_Header:
	codec_type = read_u16(f, Endianness.LE)  # codec type is in Little-endian always

	endianness: Endianness = get_game_endianness(game_version)
	scale_stream_count = read_u16(f, endianness)
	rotation_stream_count = read_u16(f, endianness)
	translation_stream_count = read_u16(f, endianness)
	prob_error_value = read_f32(f, endianness)
	prob_compression_rate = read_f32(f, endianness)

	return Base_Animation_Codec_Header(
		codec_type=codec_type,
		scale_stream_count=scale_stream_count,
		rotation_stream_count=rotation_stream_count,
		translation_stream_count=translation_stream_count,
		prob_error_value=prob_error_value,
		prob_compression_rate=prob_compression_rate
	)


def read_codec_header(
	f: BinaryIO, pointer: Base_Tag_Pointer, game_version: Game_Version
) -> Codec_Header_Union | None:
	address = pointer.get_address()
	f.seek(address)

	common_header: Base_Animation_Codec_Header = read_common_codec_header(f, game_version)

	endianness = get_game_endianness(game_version)

	header: Codec_Header_Union | None = None

	if common_header.codec_type == 0:
		frame_count = 0

		if game_version == Game_Version.D1_DEV_ALPHA:  # not sure but should be like this
			frame_count = read_u32(f, endianness)
		else:
			frame_count = read_u64(f, endianness)
		scale_stream = Vec_Pointer(f, game_version)
		rotation_stream = Vec_Pointer(f, game_version)
		translation_stream = Vec_Pointer(f, game_version)

		header = Codec_0_Header(
			codec_type=common_header.codec_type,
			scale_stream_count=common_header.scale_stream_count,
			rotation_stream_count=common_header.rotation_stream_count,
			translation_stream_count=common_header.translation_stream_count,
			prob_error_value=common_header.prob_error_value,
			prob_compression_rate=common_header.prob_compression_rate,
			frame_count=frame_count,
			scale_stream_pointer=scale_stream,
			rotation_stream_pointer=rotation_stream,
			translation_stream_pointer=translation_stream
		)

	elif common_header.codec_type == 1:
		uncompressed_data = Vec_Pointer(f, game_version)
		compressed_data = Vec_Pointer(f, game_version)
		keyframe_deltas = Vec_Pointer(f, game_version)
		interpolation_data = Vec_Pointer(f, game_version)
		quantization_minimums = Vec_Pointer(f, game_version)
		quantization_extents = Vec_Pointer(f, game_version)
		array_7 = Vec_Pointer(f, game_version)

		header = Codec_1_Header(
			codec_type=common_header.codec_type,
			scale_stream_count=common_header.scale_stream_count,
			rotation_stream_count=common_header.rotation_stream_count,
			translation_stream_count=common_header.translation_stream_count,
			prob_error_value=common_header.prob_error_value,
			prob_compression_rate=common_header.prob_compression_rate,
			uncompressed_data_pointer=uncompressed_data,
			compressed_data_pointer=compressed_data,
			keyframe_deltas_pointer=keyframe_deltas,
			interpolation_data_pointer=interpolation_data,
			quantization_minimums_pointer=quantization_minimums,
			quantization_extents_pointer=quantization_extents,
			array_7_pointer=array_7
		)

	elif common_header.codec_type == 2:
		frame_count = 0

		if game_version == Game_Version.D1_DEV_ALPHA:
			frame_count = read_u32(f, endianness)
		else:
			frame_count = read_u64(f, endianness)
		stream_data = Vec_Pointer(f, game_version)
		quantization_minimums = Vec_Pointer(f, game_version)
		quantization_extents = Vec_Pointer(f, game_version)

		header = Codec_2_Header(
			codec_type=common_header.codec_type,
			scale_stream_count=common_header.scale_stream_count,
			rotation_stream_count=common_header.rotation_stream_count,
			translation_stream_count=common_header.translation_stream_count,
			prob_error_value=common_header.prob_error_value,
			prob_compression_rate=common_header.prob_compression_rate,
			frame_count=frame_count,
			stream_data_pointer=stream_data,
			quantization_minimums_pointer=quantization_minimums,
			quantization_extents_pointer=quantization_extents
		)

	elif common_header.codec_type == 3:
		frame_count = read_u32(f, endianness)

		scale_stream_quantization = read_f32_array(f, endianness, 2)
		translation_stream_quantization = (read_f32_array(f, endianness, 3), read_f32_array(f, endianness, 3))

		if game_version != Game_Version.D1_DEV_ALPHA:  # TODO: verify
			f.seek(4, 1)  # 4 bytes of padding

		stream_pointer = Vec_Pointer(f, game_version)

		header = Codec_3_Header(
			codec_type=common_header.codec_type,
			scale_stream_count=common_header.scale_stream_count,
			rotation_stream_count=common_header.rotation_stream_count,
			translation_stream_count=common_header.translation_stream_count,
			prob_error_value=common_header.prob_error_value,
			prob_compression_rate=common_header.prob_compression_rate,
			frame_count=frame_count,
			scale_stream_quantization=scale_stream_quantization,
			translation_stream_quantization=translation_stream_quantization,
			stream_data_pointer=stream_pointer
		)
	else:
		logger.warning(f"Animated data codec is not type 0, 1 or 2, it is: {common_header.codec_type}")
		return None

	return header


def read_codec_buffers(
	f: BinaryIO,
	codec_header: Codec_Header_Union | None
) -> Codec_Buffers_Union | None:
	if isinstance(codec_header, Codec_0_Header):
		return read_codec_0_buffers(f, codec_header)
	elif isinstance(codec_header, Codec_1_Header):
		return read_codec_1_buffers(f, codec_header)
	elif isinstance(codec_header, Codec_2_Header):
		return read_codec_2_buffers(f, codec_header)
	elif isinstance(codec_header, Codec_3_Header):
		return read_codec_3_buffers(f, codec_header)
	else:
		return None


def read_codec_0_buffers(f: BinaryIO, codec_header: Codec_0_Header) -> Codec_0_Buffers:
	animated_scale_stream = Tag_Array_NP(f, codec_header.scale_stream_pointer, np.float32)
	animated_rotation_stream = Tag_Array_NP(f, codec_header.rotation_stream_pointer, np.float32, 4)
	animated_translation_stream = Tag_Array_NP(f, codec_header.translation_stream_pointer, np.float32, 4)

	return Codec_0_Buffers(animated_scale_stream, animated_rotation_stream, animated_translation_stream)


def read_codec_1_buffers(f: BinaryIO, codec_header: Codec_1_Header) -> Codec_1_Buffers:
	uncompressed_data = Tag_Array_NP(f, codec_header.uncompressed_data_pointer, np.int16)
	compressed_data = Tag_Array_NP(f, codec_header.compressed_data_pointer, np.int16)
	keyframe_deltas = Tag_Array_NP(f, codec_header.keyframe_deltas_pointer, np.uint8)
	interpolation_data = Tag_Array_NP(f, codec_header.interpolation_data_pointer, np.uint8)
	quantization_minimums = Tag_Array_NP(f, codec_header.quantization_minimums_pointer, np.float32)
	quantization_extents = Tag_Array_NP(f, codec_header.quantization_extents_pointer, np.float32)
	array_7 = Tag_Array_NP(f, codec_header.array_7_pointer, np.int16)

	return Codec_1_Buffers(
		uncompressed_data,
		compressed_data,
		keyframe_deltas,
		interpolation_data,
		quantization_minimums,
		quantization_extents,
		array_7
	)


def read_codec_2_buffers(f: BinaryIO, codec_header: Codec_2_Header) -> Codec_2_Buffers:
	stream_data = Tag_Array_NP(f, codec_header.stream_data_pointer, np.uint16)
	quantization_minimums = Tag_Array_NP(f, codec_header.quantization_minimums_pointer, np.float32)
	quantization_extents = Tag_Array_NP(f, codec_header.quantization_extents_pointer, np.float32)

	return Codec_2_Buffers(stream_data, quantization_minimums, quantization_extents)


def read_codec_3_buffers(f: BinaryIO, codec_header: Codec_3_Header) -> Codec_3_Buffers:
	stream_data = Tag_Array_NP(f, codec_header.stream_data_pointer, np.uint16)

	return Codec_3_Buffers(stream_data)


def read_animation(f: BinaryIO, game_version: Game_Version) -> Animation_Data:
	# read general codec
	animation_header: Animation_Header = read_animation_header(f, 0, game_version)

	# parse control maps
	control_maps = read_control_maps(f, animation_header, game_version)
	rig_components = Tag_Array(f, animation_header.rig_components_array_pointer, read_rig_component)

	# read static data header
	static_bones_header = None
	static_bones_buffers = None

	if not animation_header.static_bone_data_pointer.is_zero():
		static_bones_header = read_codec_header(f, animation_header.static_bone_data_pointer, game_version)

		if static_bones_header is not None:
			if static_bones_header.codec_type != 3:
				raise Exception(f"Static codec {static_bones_header.codec_type} is not supported")

			static_bones_buffers = read_codec_buffers(f,  static_bones_header)

	animated_bones_header = None
	animated_bones_buffers = None

	if not animation_header.animated_bone_data_pointer.is_zero():
		# read animated data header
		animated_bones_header = read_codec_header(f, animation_header.animated_bone_data_pointer, game_version)

		if animated_bones_header is not None:
			if animated_bones_header.codec_type > 3 or animated_bones_header.codec_type < 0:
				raise Exception(F"Parsing animation file // Error: Animated codec {animated_bones_header.codec_type} is not supported")

			animated_bones_buffers = read_codec_buffers(f, animated_bones_header)

	return Animation_Data(
		animation_header,
		static_bones_header,
		static_bones_buffers,
		animated_bones_header,
		animated_bones_buffers,
		control_maps,
		rig_components
	)

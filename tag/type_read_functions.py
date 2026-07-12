import struct
from typing import BinaryIO

from .game_version import Game_Version
from .endianness import get_game_endianness, Endianness
from .data_structures import Rig_Component, Transform, Skeleton_Node_Def, Control_Relation, Control_Relation_D2


def read_pointer_block(f: BinaryIO, game_version: Game_Version) -> int:
	if game_version == Game_Version.D1_DEV_ALPHA:
		return read_u32(f, get_game_endianness(game_version))
	else:
		return read_u64(f, get_game_endianness(game_version))


def read_u32(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness} I", f.read(4))[0]


def read_u32_array(f: BinaryIO, endianness: Endianness, length) -> tuple[int, ...]:
	return struct.unpack(f"{endianness} {length}I", f.read(4 * length))


def read_s32(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}i", f.read(4))[0]


def read_u64(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}Q", f.read(8))[0]


def read_u16(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}H", f.read(2))[0]


def read_u16_array(f: BinaryIO, endianness: Endianness, length) -> tuple[int, ...]:
	return struct.unpack(f"{endianness} {length}H", f.read(2 * length))


def read_s16(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}h", f.read(2))[0]


def read_u8(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}B", f.read(1))[0]


def read_u8_array(f: BinaryIO, endianness: Endianness, length):
	return struct.unpack(f"{endianness} {length}B", f.read(length))


def read_s8(f: BinaryIO, endianness: Endianness) -> int:
	return struct.unpack(f"{endianness}b", f.read(1))[0]


def read_s8_array(f: BinaryIO, endianness: Endianness, length) -> tuple[int, ...]:
	return struct.unpack(f"{endianness} {length}b", f.read(length))


def read_f32(f: BinaryIO, endianness: Endianness) -> float:
	return struct.unpack(f"{endianness}f", f.read(4))[0]


def read_f32_array(f: BinaryIO, endianness: Endianness, length) -> tuple[float, ...]:
	return struct.unpack(f"{endianness} {length}f", f.read(4 * length))


def read_vec4(f: BinaryIO, endianness: Endianness) -> tuple[float, float, float, float]:
	return struct.unpack(f"{endianness} {4}f", f.read(16))


# additional types
def read_rig_component(f: BinaryIO, endianness: Endianness) -> Rig_Component:
	return Rig_Component(read_u32(f, endianness), read_u32(f, Endianness.LE))  # wtf


def read_transform(f: BinaryIO, endianness: Endianness) -> Transform:
	return Transform(read_vec4(f, endianness), read_vec4(f, endianness))


def read_bone_relation(f: BinaryIO, endianness: Endianness) -> Skeleton_Node_Def:
	bone_hash = read_u32(f, endianness)
	parent_node_index = read_s32(f, endianness)
	first_child_node_index = read_s32(f, endianness)
	next_sibling_node_index = read_s32(f, endianness)

	return Skeleton_Node_Def(bone_hash, parent_node_index, first_child_node_index, next_sibling_node_index)


def read_control_relation_d1(f: BinaryIO, endianness: Endianness) -> Control_Relation:
	payload_1 = (
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, Endianness.LE),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f,  Endianness.LE),
	)

	coof_1 = read_f32(f, endianness)

	payload_2 = (
		read_s32(f, Endianness.LE),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, Endianness.LE),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, Endianness.LE),
	)

	coof_2 = read_f32(f, endianness)

	payload_3 = (
		read_s32(f, Endianness.LE),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
	)

	return Control_Relation(payload_1, coof_1, payload_2, coof_2, payload_3)


def read_control_relation_d2(f: BinaryIO, endianness: Endianness) -> Control_Relation_D2:
	hash = read_u32(f, endianness)
	payload_1 = (
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
	)

	coof_1 = read_f32(f, endianness)

	payload_2 = (
		read_s32(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
	)

	coof_2 = read_f32(f, endianness)

	payload_3 = (
		read_s32(f, endianness),
		read_s16(f, endianness),
		read_s16(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
		read_s8(f, endianness),
	)

	return Control_Relation_D2(payload_1, coof_1, payload_2, coof_2, payload_3, hash)
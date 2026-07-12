from dataclasses import dataclass
from typing import BinaryIO

from tag.tag_pointers import Vec_Pointer, Base_Tag_Pointer
from tag.tag_array import Tag_Array
from tag.game_version import Game_Version
from tag.data_structures import Rig_Component, Control_Relation, Transform
from tag.type_read_functions import read_u32, read_control_relation_d1, read_control_relation_d2, read_s16, \
	read_rig_component, read_transform
from tag.endianness import get_game_endianness, Endianness
from .read_s_pattern_component import S_Pattern_Component_Header, read_s_pattern_component_header
from fnv_hashes.int_to_hex import u32_to_be_hex


rig_secondary_classes = {
	Game_Version.D1_DEV_ALPHA: 0x80800A98,
	Game_Version.D1_ROI: 0x808008B2,
	Game_Version.D2_EOF: 0x80808B66,
	Game_Version.MARATHON: 0x8080AD85
}


@dataclass(slots=True)
class Runtime_Rig_Main_Struct:
	rig_components_pointer: Vec_Pointer
	controls_relations_pointer: Vec_Pointer
	controls_transforms_pointer: Vec_Pointer
	bone_to_control_pointer: Vec_Pointer
	control_to_bone_pointer: Vec_Pointer
	control_name_to_bone_index_pointer: Vec_Pointer


@dataclass(slots=True)
class Runtime_Rig_Data:
	rig_components: Tag_Array[Rig_Component]
	controls_relations: Tag_Array[Control_Relation]
	controls_transforms: Tag_Array[Transform]
	bone_to_control: Tag_Array[int]
	control_to_bone: Tag_Array[int]
	control_name_to_bone_index: Tag_Array[Rig_Component]


class Rig_Secondary_Class_Mismatch_Exception(Exception):
	pass


def test_rig_secondary_class(f: BinaryIO, pointer_0x10: Base_Tag_Pointer, game_version: Game_Version) -> tuple[int, int]:
	address = pointer_0x10.get_address()

	f.seek(address - 4)  # 4 bytes before

	secondary_class = read_u32(f, get_game_endianness(game_version))

	return rig_secondary_classes[game_version], secondary_class


def read_runtime_rig_main_struct(f: BinaryIO, pointer: Base_Tag_Pointer, game_version: Game_Version) -> Runtime_Rig_Main_Struct:
	padding = {
		Game_Version.D1_DEV_ALPHA: 68,
		Game_Version.D1_ROI: 8 * 16,
		Game_Version.D2_EOF: 10 * 16 + 8,
		Game_Version.MARATHON: 10 * 16 + 8
	}

	address = pointer.get_address()
	f.seek(address + padding[game_version])

	endianness = get_game_endianness(game_version)

	rig_components_pointer = Vec_Pointer(f, game_version)
	controls_relations_pointer = Vec_Pointer(f, game_version)
	controls_transforms_pointer = Vec_Pointer(f, game_version)
	unk_pointer_0 = Vec_Pointer(f, game_version)

	some_tag = read_u32(f, endianness)

	if game_version != Game_Version.D1_DEV_ALPHA:
		f.seek(4, 1)  # some_num = read_u32(f)

	bone_to_control_pointer = Vec_Pointer(f, game_version)
	control_to_bone_pointer = Vec_Pointer(f, game_version)

	if game_version == Game_Version.D1_DEV_ALPHA:
		f.seek(12, 1)
	else:
		f.seek(24, 1)

	control_name_to_bone_index_pointer = Vec_Pointer(f, game_version)

	return Runtime_Rig_Main_Struct(
		rig_components_pointer=rig_components_pointer,
		controls_relations_pointer=controls_relations_pointer,
		controls_transforms_pointer=controls_transforms_pointer,
		bone_to_control_pointer=bone_to_control_pointer,
		control_to_bone_pointer=control_to_bone_pointer,
		control_name_to_bone_index_pointer=control_name_to_bone_index_pointer
	)


def read_runtime_rig_data(f: BinaryIO, main_struct: Runtime_Rig_Main_Struct, game_version: Game_Version) -> Runtime_Rig_Data:
	relations_functions = {
		Game_Version.D1_DEV_ALPHA: read_control_relation_d1,
		Game_Version.D1_ROI: read_control_relation_d1,
		Game_Version.D2_EOF: read_control_relation_d2,
		Game_Version.MARATHON: read_control_relation_d2
	}

	rig_components = Tag_Array(f, main_struct.rig_components_pointer, read_rig_component)
	controls_relations = Tag_Array(f, main_struct.controls_relations_pointer, relations_functions[game_version])
	# seem to be local transforms????
	controls_transforms = Tag_Array(f, main_struct.controls_transforms_pointer, read_transform)
	bone_to_control = Tag_Array(f, main_struct.bone_to_control_pointer, read_s16)
	control_to_bone = Tag_Array(f, main_struct.control_to_bone_pointer, read_s16)
	control_name_to_bone_index = Tag_Array(f, main_struct.control_name_to_bone_index_pointer, read_rig_component)


	return Runtime_Rig_Data(
		rig_components=rig_components,
		controls_relations=controls_relations,
		controls_transforms=controls_transforms,
		bone_to_control=bone_to_control,
		control_to_bone=control_to_bone,
		control_name_to_bone_index=control_name_to_bone_index
	)


def read_runtime_rig(f: BinaryIO, game_version) -> Runtime_Rig_Data:
	header: S_Pattern_Component_Header = read_s_pattern_component_header(f, game_version)

	required_class, read_class = test_rig_secondary_class(f, header.default_instance_pointer, game_version)

	if required_class != read_class:
		raise Rig_Secondary_Class_Mismatch_Exception(f"Rig secondary class for game [{game_version.value}] should be 0x{u32_to_be_hex(required_class)}, not 0x{u32_to_be_hex(read_class)}")

	main_struct: Runtime_Rig_Main_Struct = read_runtime_rig_main_struct(f, header.definition_pointer, game_version)
	runtime_rig_data = read_runtime_rig_data(f, main_struct, game_version)

	return runtime_rig_data

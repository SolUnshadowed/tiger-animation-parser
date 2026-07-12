import json
import numpy.typing as npt
import numpy as np

from dataclasses import dataclass
from typing import BinaryIO
from pyglm import glm

from tag.game_version import Game_Version
from tag.tag_pointers import Vec_Pointer, Base_Tag_Pointer
from tag.tag_array import Tag_Array
from tag.type_read_functions import read_u32, read_bone_relation, read_transform
from tag.endianness import get_game_endianness, Endianness
from tag.data_structures import Skeleton_Node_Def, Transform
from matrix_operations.glm_matrix_operations import glm_compose_mat4
from fnv_hashes.int_to_hex import u32_to_be_hex
from fnv_hashes.bones_names import hash_to_bungie_name
from .read_s_pattern_component import S_Pattern_Component_Header, read_s_pattern_component_header


skeleton_secondary_classes = {
	Game_Version.D1_DEV_ALPHA: 0x80800DC9,
	Game_Version.D1_ROI: 0x808006BD,
	Game_Version.D2_EOF: 0x808081DD,
	Game_Version.MARATHON: 0x80809FB6
}


# Tiger
# 	Z-up
# 	X-forward
# 	Y-right
# Three.js
# 	Y-up
#	Z-forward
#	X-right
# Tiger to Three.js
# [x, y, z] -> [y, z, x]
#  x  y  z      x  y  z
#  x_new = y_old
#  y_new = z_old
#  z_new = x_old

def transform_to_glm_mat4(transform: Transform):
	ts = transform.ts
	r = transform.r

	scale = glm.vec3(ts[3], ts[3], ts[3])

	# [x, y, z] -> [y, z, x]
	translation = glm.vec3(ts[1], ts[2], ts[0])

	# [x, y, z] -> [y, z, x], but w is on 0th place (w, x, y, z) in glm quats
	quat = glm.quat(r[3], r[1], r[2], r[0])

	return glm_compose_mat4(translation, quat, scale)


def transform_to_np_matrix(transform: Transform):
	return np.array(transform_to_glm_mat4(transform))


@dataclass(slots=True)
class Skeleton_Main_Struct:
	bone_hierarchy_pointer: Vec_Pointer
	default_obj_space_tr_pointer: Vec_Pointer
	default_inv_obj_space_tr_pointer: Vec_Pointer


class Skeleton:
	__slots__ = [
		"node_defs",
		"default_obj_space_tr",
		"default_inv_obj_space_tr",
		"default_obj_space_matrices",
		"default_inv_obj_space_matrices",
		"bone_to_parent_offset"
	]

	node_defs: Tag_Array[Skeleton_Node_Def]
	default_obj_space_tr: Tag_Array[Transform]
	default_inv_obj_space_tr: Tag_Array[Transform]
	default_obj_space_matrices: list[npt.NDArray]
	default_inv_obj_space_matrices: list[npt.NDArray]
	bone_to_parent_offset: list[npt.NDArray]


	def __init__(self, node_defs, default_obj_space_tr, default_inv_obj_space_tr):
		self.node_defs = node_defs
		self.default_obj_space_tr = default_obj_space_tr
		self.default_inv_obj_space_tr = default_inv_obj_space_tr

		default_obj_space_tr = default_obj_space_tr
		default_inv_obj_space_tr = default_inv_obj_space_tr

		# compute reference bone matrices
		self.default_obj_space_matrices = [transform_to_glm_mat4(transform) for transform in default_obj_space_tr]
		self.default_inv_obj_space_matrices = [transform_to_glm_mat4(transform) for transform in default_inv_obj_space_tr]
		self.bone_to_parent_offset = []

		# compute bone to parent offsets
		for bone_index, current_bone_matrix in enumerate(self.default_obj_space_matrices):
			bone_relation = node_defs[bone_index]
			parent_bone_index = bone_relation.parent_node_index

			if parent_bone_index > -1:
				parent_bone = self.default_inv_obj_space_matrices[parent_bone_index]
				parent_offset_matrix = parent_bone * current_bone_matrix
				self.bone_to_parent_offset.append(parent_offset_matrix)
			else:
				self.bone_to_parent_offset.append(glm.mat4(current_bone_matrix))


class Skeleton_Secondary_Class_Mismatch_Exception(Exception):
	pass


def create_api_like_skeleton(skeleton_data: Skeleton):
	nodes = []

	for node_def in skeleton_data.node_defs:

		res = {
			"name": {
				"hash": node_def.bone_hash,
				"string":  hash_to_bungie_name[node_def.bone_hash] if node_def.bone_hash in hash_to_bungie_name else "???"
			},
			"parent_node_index": node_def.parent_node_index,
			"first_child_node_index": node_def.first_child_node_index,
			"next_sibling_node_index": node_def.next_sibling_node_index,
		}

		nodes.append(res)

	default_object_space_transforms = []

	for node_def in skeleton_data.default_obj_space_tr:
		default_object_space_transforms.append(node_def)

	default_inverse_object_space_transforms = []

	for node_def in skeleton_data.default_inv_obj_space_tr:
		default_inverse_object_space_transforms.append(node_def)

	return {
		"definition": {
			"nodes": nodes,
			"default_object_space_transforms": default_object_space_transforms,
			"default_inverse_object_space_transforms": default_inverse_object_space_transforms
		}
	}


def save_api_like_skeleton(file_name, data):
	with open(file_name, "w") as json_file:
		json.dump(data, json_file, indent=2)


def test_skeleton_secondary_class(f: BinaryIO, pointer_0x10: Base_Tag_Pointer, game_version: Game_Version) -> tuple[int, int]:
	address = pointer_0x10.get_address()

	f.seek(address - 4)  # 4 bytes before

	secondary_class = read_u32(f, get_game_endianness(game_version))

	return skeleton_secondary_classes[game_version], secondary_class


def read_skeleton_main_struct(f: BinaryIO, pointer: Base_Tag_Pointer, game_version: Game_Version) -> Skeleton_Main_Struct:
	padding = {
		Game_Version.D1_DEV_ALPHA: 88,
		Game_Version.D1_ROI: 8 * 16 + 8,
		Game_Version.D2_EOF: 9 * 16,
		Game_Version.MARATHON: 12 * 16
	}

	endianness = get_game_endianness(game_version)

	address = pointer.get_address()
	f.seek(address + padding[game_version])

	bone_hierarchy_pointer = Vec_Pointer(f, game_version)
	obj_space_tr_pointer = Vec_Pointer(f, game_version)
	inv_obj_space_tr_pointer = Vec_Pointer(f, game_version)
	# range_index_map_pointer = Vec_pointer(f)
	# inner_index_map = Vec_pointer(f)

	return Skeleton_Main_Struct(
		bone_hierarchy_pointer=bone_hierarchy_pointer,
		default_obj_space_tr_pointer=obj_space_tr_pointer,
		default_inv_obj_space_tr_pointer=inv_obj_space_tr_pointer
	)


def read_skeleton_data(f: BinaryIO, main_struct: Skeleton_Main_Struct) -> Skeleton:
	bone_hierarchy = Tag_Array(f, main_struct.bone_hierarchy_pointer, read_bone_relation)
	obj_space_tr = Tag_Array(f, main_struct.default_obj_space_tr_pointer, read_transform)
	inv_obj_space_tr = Tag_Array(f, main_struct.default_inv_obj_space_tr_pointer, read_transform)

	return Skeleton(
		node_defs=bone_hierarchy,
		default_obj_space_tr=obj_space_tr,
		default_inv_obj_space_tr=inv_obj_space_tr
	)


def read_skeleton(f: BinaryIO, game_version: Game_Version) -> Skeleton:
	header: S_Pattern_Component_Header = read_s_pattern_component_header(f, game_version)

	required_class, read_class = test_skeleton_secondary_class(f, header.default_instance_pointer, game_version)

	if required_class != read_class:
		raise Skeleton_Secondary_Class_Mismatch_Exception(f"Skeleton secondary class for game [{game_version.value}] should be 0x{u32_to_be_hex(required_class)}, not 0x{u32_to_be_hex(read_class)}")

	main_struct: Skeleton_Main_Struct = read_skeleton_main_struct(f, header.definition_pointer, game_version)
	skeleton: Skeleton = read_skeleton_data(f, main_struct)

	return skeleton

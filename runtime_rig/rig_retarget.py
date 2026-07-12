import logging
import time
import numpy as np

from pyglm import glm
from dataclasses import dataclass

from tag.tag_array import Tag_Array
from tag.data_structures import Skeleton_Node_Def, Rig_Component
from matrix_operations.glm_matrix_operations import (
	glm_get_scale, glm_get_quat, glm_get_translation,
	glm_decompose_mat4, glm_compose_mat4,
)
from tag_readers.read_animation import Animation_Data
from tag_readers.read_skeleton import Skeleton
from tag_readers.read_rig import Runtime_Rig_Data
from animation_decoding.decode_animation import Bone_Tracks
from fnv_hashes.int_to_hex import u32_to_be_hex
from .rig_constraints import (
	fill_constraints, Constraint, Constraint_Type,
	IK_Function_Type, Space_Type, Space_Def
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IK_Affected_Control:
	affector_control_index: int
	affected_control_index: int


@dataclass(slots=True)
class IK_3_Chain:
	start_bone_index: int
	target_bone_index: int
	end_bone_index: int


@dataclass(slots=True)
class RFK_Chain:
	start_bone_index: int
	end_bone_index: int
	bones_indices: tuple[int, ...]


@dataclass(slots=True)
class Runtime_Rig_Cache:
	constraints: list[Constraint]
	ik_3_chains: dict[int, IK_3_Chain]
	rfk_chains: dict[int, RFK_Chain]
	ik_affected_controls: list[IK_Affected_Control]


@dataclass(slots=True)
class Animation_Cache:
	ignored_controls: set[int]


class Invalid_Rig_Error(Exception):
	pass


def log_rig_cache(rig_cache: Runtime_Rig_Cache) -> None:
	logger.info("Rig cache:")
	for ik_3_chain_affector in rig_cache.ik_3_chains:
		chain = rig_cache.ik_3_chains[ik_3_chain_affector]
		logger.info(f"\tbone {ik_3_chain_affector} is end for chain: [{chain.start_bone_index}, {chain.target_bone_index}, {chain.end_bone_index}]")

	for rfk_chain_affector in rig_cache.rfk_chains:
		chain = rig_cache.rfk_chains[rfk_chain_affector]
		logger.info(f"\tbone {rfk_chain_affector} is end for chain: {chain.bones_indices}")


def sign(val: float | int):
	if val >= 0:
		return 1
	return -1


def calc_control_limit(rig: Runtime_Rig_Data, animation_rig_components: Tag_Array[Rig_Component]):
	logger.info("Runtime rig subsets limit:")
	limit = 0

	rig_components_len = rig.rig_components.length
	animation_components_len = animation_rig_components.length

	for i in range(min(rig_components_len, animation_components_len)):
		rig_component_hash = rig.rig_components[i].hash
		rig_component_count = rig.rig_components[i].count
		animation_component_hash = animation_rig_components[i].hash
		animation_component_count = animation_rig_components[i].count

		if rig_component_hash == animation_component_hash:
			if rig_component_count == animation_component_count:
				limit += rig_component_count
				logger.info(f"\tuse subset [{i}], {u32_to_be_hex(rig_component_hash)}, control count: {rig_component_count}")
			else:
				limit += min(rig_component_count, animation_component_count)
				logger.info(f"\tuse subset [{i}] part, {u32_to_be_hex(rig_component_hash)}, control count: {min(rig_component_count, animation_component_count)}")
				break

	return limit


def build_bone_chain(
	skeleton_node_defs: Tag_Array[Skeleton_Node_Def],
	start_bone_index: int,
	end_bone_index: int
) -> tuple[int, ...]:
	chain = [end_bone_index]
	curr = end_bone_index

	while curr != start_bone_index:
		curr = skeleton_node_defs[curr].parent_node_index

		if curr == -1:
			raise Invalid_Rig_Error(
				f"IK chain start bone {end_bone_index} is not an ancestor of {start_bone_index}"
			)

		chain.append(curr)

	return tuple(reversed(chain))


def build_runtime_rig_cache(skeleton: Skeleton, rig: Runtime_Rig_Data) -> Runtime_Rig_Cache:
	constraints = fill_constraints(rig)
	bone_to_control = rig.bone_to_control
	bones_relations = skeleton.node_defs

	ik_affected_controls = []
	ik_3_chains = {}
	rfk_chains = {}

	for control_index in range(len(constraints)):
		constraint = constraints[control_index]
		bone_index = constraint.bone_index  # current bone is an end of a chain

		if constraint.ik_function_type == IK_Function_Type.RFK:
			chain = build_bone_chain(bones_relations, constraint.ik_chain_start_bone_index, bone_index)

			rfk_chains[bone_index] = RFK_Chain(
				start_bone_index=chain[0],
				end_bone_index=chain[-1],
				bones_indices=chain
			)

			for i in range(1, len(chain) - 1):
				ik_affected_controls.append(
					IK_Affected_Control(control_index, bone_to_control[chain[i]])
				)

		if constraint.ik_function_type == IK_Function_Type.IK_3:
			chain = build_bone_chain(bones_relations, constraint.ik_chain_start_bone_index, bone_index)

			if len(chain) != 3:
				raise Invalid_Rig_Error(
					f"IK_3 chain must have length 3, got {len(chain)}, start {chain[0]}, end {chain[-1]}"
				)

			ik_3_chains[bone_index] = IK_3_Chain(chain[0], chain[1], chain[2])

			target_bone_index = chain[1]

			ik_affected_controls.append(
				IK_Affected_Control(control_index, bone_to_control[target_bone_index])
			)

	return Runtime_Rig_Cache(
		constraints=constraints,
		ik_3_chains=ik_3_chains,
		rfk_chains=rfk_chains,
		ik_affected_controls=ik_affected_controls
	)


def build_animation_cache(tracks: list[Bone_Tracks], ik_affected_controls: list[IK_Affected_Control]) -> Animation_Cache:
	bone_data: list[Bone_Tracks] = tracks

	ignored_controls = set()

	for i in range(len(ik_affected_controls)):
		affector_control_index = ik_affected_controls[i].affector_control_index
		affected_control_index = ik_affected_controls[i].affected_control_index

		if affected_control_index == -1:
			continue
		elif affected_control_index > affector_control_index: # if affected is after affector
			track_group: Bone_Tracks = bone_data[affected_control_index]

			# if bone is static through the whole animation and its control is after ik affector it will override srt data
			# hence static controls should be ignored
			attrs = [track_group.scales, track_group.rotations, track_group.translations]
			if all(x is None or len(x) < 2 for x in attrs):
				ignored_controls.add(affected_control_index)

	return Animation_Cache(ignored_controls)


def get_frame_value(attr, default, frame_index):
	if attr is not None:
		return attr[frame_index % attr.shape[0]]

	return default


def rig_retarget(
	animation_data: Animation_Data,
	controls_data: list[Bone_Tracks],
	skeleton: Skeleton,
	rig: Runtime_Rig_Data,
	fix_replacement_layer=True
):
	# animation properties
	frames = animation_data.animation_header.frame_count
	# object properties
	object_matrix = glm.mat4()
	aim_vector = glm.vec3(0, 0, 1)
	neutral_aim_vector = glm.vec3(0, 0, 1)
	# compute skeleton cache
	bones_relations = skeleton.node_defs
	bone_object_space_matrices = skeleton.default_obj_space_matrices
	bone_to_parent_offset = skeleton.bone_to_parent_offset
	num_bones = bones_relations.length
	# compute rig and skeleton cache
	rig_cache = build_runtime_rig_cache(skeleton, rig)
	log_rig_cache(rig_cache)
	constraints: list[Constraint] = rig_cache.constraints

	bone_to_control = rig.bone_to_control
	control_to_bone = rig.control_to_bone
	# compute animation cache
	animation_cache = build_animation_cache(controls_data, rig_cache.ik_affected_controls)
	ignored_ik_affected_controls = animation_cache.ignored_controls

	logger.info("Ignored controls:")
	for ignored in ignored_ik_affected_controls:
		logger.info(f"\tcontrol {ignored} [bone {control_to_bone[ignored]}]")

	# intermediate storage
	skeleton_bones_matrices = glm.array.zeros(num_bones, glm.mat4)
	# result animation defaults
	converted_animation = [
		Bone_Tracks(
			bone_name_hash=bones_relations[bone_index].bone_hash,
			scales=np.ones((frames, 3), dtype=np.float32),  # 1.0
			rotations=np.zeros((frames, 4), dtype=np.float32),  # [0,0,0,1]
			translations=np.zeros((frames, 3), dtype=np.float32)  # 0.0
		) for bone_index in range(num_bones)
	]
	for track in converted_animation:
		track.rotations[:, 3] = 1.0

	# bone controls matrices, limit by compatible layers
	controls_limit = calc_control_limit(rig, animation_data.runtime_rig_components)
	logger.info(f"Controls limit: {controls_limit}")

	for control_index in range(0, controls_limit):
		bone_index = control_to_bone[control_index]
		track_group: Bone_Tracks = controls_data[control_index]

		# animation has no tracks for control
		if track_group.scales is None and track_group.rotations is None  and track_group.translations  is None :
			logger.info(
				f"\tbone [{bone_index}] {u32_to_be_hex(bones_relations[bone_index].bone_hash)} has no tracks, fix will be used" if fix_replacement_layer else "fix will not be used"
			)

	logger.info("Retarget started")
	start_time = time.perf_counter()

	for frame in range(frames):
		is_bone_updated = np.zeros((num_bones), dtype=np.bool)

		aim_quat = glm.quat(neutral_aim_vector, aim_vector) # rotation_from_unit_vectors(neutral_aim_vector, aim_vector)

		for control_index in range(0, controls_limit):

			# static bone should not override ik
			if control_index in ignored_ik_affected_controls:
				continue

			bone_index = control_to_bone[control_index]
			track_group: Bone_Tracks = controls_data[control_index]
			constraint = constraints[control_index]

			scale = glm.vec3(get_frame_value(track_group.scales, np.array([1, 1, 1]), frame))
			rotation = get_frame_value(track_group.rotations, np.array([0, 0, 0, 1]), frame)
			translation = glm.vec3(get_frame_value(track_group.translations, np.array([0, 0, 0]), frame))

			if (
				track_group.scales is None and track_group.rotations is None and
				track_group.translations is None and fix_replacement_layer
			): # fix branch
				skeleton_node_def = bones_relations[bone_index]
				parent_bone_index = skeleton_node_def.parent_node_index

				if parent_bone_index > -1 and is_bone_updated[parent_bone_index]:
					parent_matrix = skeleton_bones_matrices[parent_bone_index]
					origin_tr = glm_get_translation(parent_matrix)
					origin_rot = glm_get_quat(parent_matrix)

					parent_offset_matrix = bone_to_parent_offset[bone_index]
					parent_offset_tr = glm_get_translation(parent_offset_matrix)
					parent_offset_rot = glm_get_quat(parent_offset_matrix)

					result_tr = origin_tr + origin_rot * parent_offset_tr  # not adding animation data as it is identity
					result_rot = origin_rot * parent_offset_rot

					skeleton_bones_matrices[bone_index] = glm_compose_mat4(result_tr, result_rot, scale)
					is_bone_updated[bone_index] = True
				else:
					skeleton_bones_matrices[bone_index] = bone_object_space_matrices[bone_index]
					is_bone_updated[bone_index] = True
			else:
				origin_rot = None
				origin_tr = None

				animation_rot = glm.quat(rotation[3], rotation[1], rotation[2], rotation[0])
				animation_tr = glm.vec3(translation[1], translation[2], translation[0])

				if constraint.constraint_type == Constraint_Type.POINT_AND_ORIENT:
					rotation_space: Space_Def = constraint.rot_space_0
					translation_space: Space_Def = constraint.tr_space_0

					match translation_space.space_type:
						case Space_Type.RELATIVE | Space_Type.UNK_3: # 0 and 3 for now
							parent_bone_index = translation_space.bone_index_0

							if not is_bone_updated[parent_bone_index] and parent_bone_index > -1:
								logger.warning(f"point_and_orient // tr constraint 'relative': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index] if parent_bone_index > -1 else object_matrix
							origin_tr = glm_get_translation(parent_matrix)

						case Space_Type.PARENT: # 1
							parent_bone_index = translation_space.bone_index_0

							if not is_bone_updated[parent_bone_index]:
								logger.warning(f"point_and_orient // tr constraint 'parent': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index]
							parent_tr = glm_get_translation(parent_matrix)
							parent_rot = glm_get_quat(parent_matrix)

							parent_offset_matrix = bone_to_parent_offset[bone_index]
							parent_offset_tr = glm_get_translation(parent_offset_matrix)

							origin_tr = parent_tr + parent_rot * parent_offset_tr

						case Space_Type.OBJECT:  # 2
							origin_tr = glm_get_translation(object_matrix)

						case Space_Type.BIND:  # 4
							bind_matrix = bone_object_space_matrices[bone_index]
							origin_tr = glm_get_translation(bind_matrix)

						case Space_Type.AVERAGE:
							parent_bone_index_0 = translation_space.bone_index_0
							parent_bone_index_1 = translation_space.bone_index_1

							if not is_bone_updated[parent_bone_index_0]:
								logger.warning(f"point_and_orient // tr constraint 'average': bone 0 {parent_bone_index_0} is not updated yet!")
								continue

							if not is_bone_updated[parent_bone_index_1]:
								logger.warning(f"point_and_orient // tr constraint 'average': bone 1 {parent_bone_index_1} is not updated yet!")
								continue

							origin_tr = 0.5 * (
								glm_get_translation(skeleton_bones_matrices[parent_bone_index_0]) +
								glm_get_translation(skeleton_bones_matrices[parent_bone_index_1])
							)
						case _:
							logger.warning("unsupported tr source for point and orient", translation_space.space_type)
							continue

					match rotation_space.space_type:
						case Space_Type.RELATIVE | Space_Type.UNK_3:  # 0 and 3 for now
							parent_bone_index = rotation_space.bone_index_0

							if not is_bone_updated[parent_bone_index] and parent_bone_index > -1:
								logger.warning(f"point_and_orient // rot constraint 'relative': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index] if parent_bone_index > -1 else object_matrix
							origin_rot = glm_get_quat(parent_matrix)

						case Space_Type.PARENT:  # 1
							parent_bone_index = rotation_space.bone_index_0

							if not is_bone_updated[parent_bone_index]:
								logger.warning(f"point_and_orient // rot constraint 'parent': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index]
							parent_rot = glm_get_quat(parent_matrix)

							parent_offset_matrix = bone_to_parent_offset[bone_index]
							parent_offset_rot = glm_get_quat(parent_offset_matrix)

							origin_rot = parent_rot * parent_offset_rot

						case Space_Type.OBJECT:  # 2
							origin_rot = glm_get_quat(object_matrix)

						case Space_Type.BIND:  # 4
							bind_matrix = bone_object_space_matrices[bone_index]
							origin_rot = glm_get_quat(bind_matrix)

						case Space_Type.AVERAGE: # 5
							parent_bone_index_0 = rotation_space.bone_index_0
							parent_bone_index_1 = rotation_space.bone_index_1

							if not is_bone_updated[parent_bone_index_0]:
								logger.warning(f"point_and_orient // rot constraint 'average': bone 0 {parent_bone_index_0} is not updated yet!")
								continue

							if not is_bone_updated[parent_bone_index_1]:
								logger.warning(f"point_and_orient // rot constraint 'average': bone 1 {parent_bone_index_1} is not updated yet!")
								continue

							parent_bone_1_rot = glm_get_quat(skeleton_bones_matrices[parent_bone_index_0])
							parent_bone_2_rot = glm_get_quat(skeleton_bones_matrices[parent_bone_index_1])

							origin_rot = glm.slerp(parent_bone_1_rot, parent_bone_2_rot, 0.5)

						case Space_Type.AIM:  # 6
							aim_influence = constraint.aim_influence

							origin_rot = glm.slerp(glm.quat(), aim_quat, aim_influence)
						case _:
							logger.warning("unsupported rotation source for point and orient {rotation_space}")
							continue

					result_tr = origin_tr + animation_tr
					result_rot = origin_rot * animation_rot

					bone_matrix = glm_compose_mat4(result_tr, result_rot, scale)
					skeleton_bones_matrices[bone_index] = bone_matrix

					is_bone_updated[bone_index] = True

				elif constraint.constraint_type == Constraint_Type.PARENT:
					rotation_space: Space_Def = constraint.rot_space_0
					# looks like tr_space 0 and 1 are not used with parent constraint
					# but if rotation_space == AIM, it has only rotation, no translation,
					# so *it seems* rot_space_1 is used as a source of translation in this case
					translation_space: Space_Def = constraint.rot_space_1

					match rotation_space.space_type:
						case Space_Type.RELATIVE | Space_Type.UNK_3:  # 0 and 3 for now
							parent_bone_index = constraint.rot_space_0.bone_index_0

							if not is_bone_updated[parent_bone_index] and parent_bone_index > -1:
								logger.warning(f"parent // rot constraint 'relative': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index] if parent_bone_index > -1 else object_matrix
							origin_tr = glm_get_translation(parent_matrix)
							origin_rot = glm_get_quat(parent_matrix)

						case Space_Type.PARENT:  # 1
							parent_bone_index = constraint.rot_space_0.bone_index_0

							if not is_bone_updated[parent_bone_index]:
								logger.warning(f"parent // rot constraint 'parent': bone {parent_bone_index} is not updated yet!")
								continue

							parent_matrix = skeleton_bones_matrices[parent_bone_index]
							parent_tr = glm_get_translation(parent_matrix)
							parent_rot = glm_get_quat(parent_matrix)

							parent_offset_matrix = bone_to_parent_offset[bone_index]
							parent_offset_tr = glm_get_translation(parent_offset_matrix)
							parent_offset_rot = glm_get_quat(parent_offset_matrix)

							origin_tr = parent_tr + parent_rot * parent_offset_tr
							origin_rot = parent_rot * parent_offset_rot

						case  Space_Type.OBJECT:  # 2
							origin_tr = glm_get_translation(object_matrix)
							origin_rot = glm_get_quat(object_matrix)

						case  Space_Type.BIND:  # 4
							bind_matrix = bone_object_space_matrices[bone_index]

							origin_tr = glm_get_translation(bind_matrix)
							origin_rot = glm_get_quat(bind_matrix)

						case  Space_Type.AVERAGE:  # 5
							parent_bone_index_0 = constraint.rot_space_0.bone_index_0
							parent_bone_index_1 = constraint.rot_space_0.bone_index_1

							if not is_bone_updated[parent_bone_index_0]:
								logger.warning(f"parent // rot constraint 'average': bone 0 {parent_bone_index_0} is not updated yet!")
								continue

							if not is_bone_updated[parent_bone_index_1]:
								logger.warning(f"parent // rot constraint 'average': bone 1 {parent_bone_index_1} is not updated yet!")
								continue

							parent_bone_1_matrix = skeleton_bones_matrices[parent_bone_index_0]
							parent_bone_1_tr = glm_get_translation(parent_bone_1_matrix)
							parent_bone_1_rot = glm_get_quat(parent_bone_1_matrix)

							parent_bone_2_matrix = skeleton_bones_matrices[parent_bone_index_1]
							parent_bone_2_tr = glm_get_translation(parent_bone_2_matrix)
							parent_bone_2_rot = glm_get_quat(parent_bone_2_matrix)

							origin_tr = 0.5 * (
								parent_bone_1_tr +
								parent_bone_2_tr
							)

							origin_rot = glm.slerp(parent_bone_1_rot, parent_bone_2_rot, 0.5)

						case Space_Type.AIM:
							aim_influence = constraint.aim_influence

							origin_tr = glm.vec3(0, 0, 0)

							origin_rot = glm.slerp(glm.quat(), aim_quat, aim_influence)

							match translation_space.space_type:
								case Space_Type.RELATIVE | Space_Type.UNK_3:
									parent_bone_index = translation_space.bone_index_0

									if not is_bone_updated[parent_bone_index] and parent_bone_index > -1:
										logger.warning(f"parent // tr constraint 'relative': bone {parent_bone_index} is not updated yet!")
										continue

									parent_matrix = skeleton_bones_matrices[parent_bone_index] if parent_bone_index > -1 else object_matrix
									origin_tr = glm_get_translation(parent_matrix)

								case Space_Type.PARENT:
									parent_bone_index = translation_space.bone_index_0

									if not is_bone_updated[parent_bone_index]:
										logger.warning(f"parent // tr constraint 'parent': bone {parent_bone_index} is not updated yet!")
										continue

									parent_matrix = skeleton_bones_matrices[parent_bone_index]
									parent_tr = glm_get_translation(parent_matrix)
									parent_rot = glm_get_quat(parent_matrix)

									parent_offset_matrix = bone_to_parent_offset[bone_index]
									parent_offset_tr = glm_get_translation(parent_offset_matrix)

									origin_tr = parent_tr + parent_rot * parent_offset_tr

								case Space_Type.AVERAGE:
									parent_1_index = translation_space.bone_index_0
									parent_2_index = translation_space.bone_index_1

									if not is_bone_updated[parent_1_index]:
										logger.warning(f"parent // tr constraint 'average': bone {parent_1_index} is not updated yet!")
										continue

									if not is_bone_updated[parent_2_index]:
										logger.warning(f"parent // tr constraint 'average': bone {parent_2_index} is not updated yet!")
										continue

									pos1 = glm_get_translation(skeleton_bones_matrices[parent_1_index])
									pos2 = glm_get_translation(skeleton_bones_matrices[parent_2_index])
									origin_tr = 0.5 * (pos1 + pos2)

					result_tr = origin_tr + origin_rot * animation_tr
					result_rot = origin_rot * animation_rot

					bone_matrix = glm_compose_mat4(result_tr, result_rot, scale)
					skeleton_bones_matrices[bone_index] = bone_matrix

					is_bone_updated[bone_index] = True

			# functions this control has

			# RFK chain
			if constraint.ik_function_type == IK_Function_Type.RFK:
				if bone_index not in rig_cache.rfk_chains:
					raise Invalid_Rig_Error(
						f"{bone_index} should be an end of IK chain, but chain not found"
					)

				chain = rig_cache.rfk_chains[bone_index]

				start_bone_index = chain.start_bone_index
				end_bone_index = chain.end_bone_index

				if not is_bone_updated[start_bone_index]:
					logger.warning(f"rfk function // start bone {start_bone_index} is not updated yet!")
					continue

				if not is_bone_updated[end_bone_index]:
					logger.warning(f"rfk function // end bone {end_bone_index} is not updated yet!")
					continue

				start_bone_quat = glm_get_quat(skeleton_bones_matrices[start_bone_index])
				end_bone_quat = glm_get_quat(skeleton_bones_matrices[end_bone_index])

				# difference between start and end
				difference_quat = glm.inverse(start_bone_quat) * end_bone_quat
				parent_mat = skeleton_bones_matrices[start_bone_index]

				N = len(chain.bones_indices)  # full chain length
				K = N - 2  # intermediate bones (without start and end)
				ident_quat = glm.quat()
				# only for bones 1..N-2
				for i in range(1, K + 1):
					t = i / (N - 1)  # t = 1/(K+1), 2/(K+1), ... K/(K+1)
					difference_quat_step = glm.slerp(ident_quat, difference_quat, t)   # slerp returns an array

					target_bone_index = chain.bones_indices[i]
					offset_mat = bone_to_parent_offset[target_bone_index]

					target_matrix = parent_mat * offset_mat
					target_tr = glm_get_translation(target_matrix)
					target_sc = glm_get_scale(target_matrix)
					target_new_rot = start_bone_quat * difference_quat_step

					new_mat = glm_compose_mat4(target_tr, target_new_rot, target_sc)

					skeleton_bones_matrices[target_bone_index] = new_mat
					parent_mat = new_mat
					is_bone_updated[target_bone_index] = True

			# IK_3 chain
			if constraint.ik_function_type == IK_Function_Type.IK_3:
				if bone_index not in rig_cache.ik_3_chains:
					raise Invalid_Rig_Error(
						f"{bone_index} should be an end of IK chain, but chain not found"
					)

				chain = rig_cache.ik_3_chains[bone_index]

				start_bone_index = chain.start_bone_index
				target_bone_index = chain.target_bone_index
				end_bone_index = chain.end_bone_index

				# select bones (not controls as ik bones have no controls, in d1 at least)

				# start is already moved in right position
				start_matrix = skeleton_bones_matrices[start_bone_index]  # shoulder / thigh
				start_sc, start_rot, start_tr = glm_decompose_mat4(start_matrix)

				target_offset_matrix = bone_to_parent_offset[target_bone_index]
				target_matrix = start_matrix * target_offset_matrix  # elbow / knee <- the one being soved
				# extract target scale, rotation, translation
				# scale and translation are already good, need to change rotation, currently it is "default"
				target_sc, target_rot, target_tr = glm_decompose_mat4(target_matrix)

				# end is already moved in right position
				end_matrix = skeleton_bones_matrices[end_bone_index]  # wrist / foot
				end_real_tr = glm_get_translation(end_matrix)  # end
				# where end would be with current target_rot end'
				end_offset_matrix = bone_to_parent_offset[end_bone_index]
				end_constrained_matrix = target_matrix * end_offset_matrix
				end_constrained_tr = glm_get_translation(end_constrained_matrix)

				# add rotation to start
				v1 = target_tr - start_tr   # shoulder -> elbow / thigh -> knee
				v2 = end_constrained_tr - start_tr
				v3 = end_real_tr - start_tr

				# |v1 x v3| = sinA * |v1| * |v3|
				# |v1|, |v3| == 1
				# |v1 x v3| = sinA
				v1_unit = glm.normalize(v1)
				cross_check = glm.length(glm.cross(v1_unit, glm.normalize(v3)))

				plane_current = glm.normalize(glm.cross(v1, v2))  # plane with end not in right position
				plane_target = None

				# angle is checked in case if chain is fully extended
				# if it is fully extended there is no plane to match, so this block will not be executed
				if cross_check > 0.0872:
					plane_target = glm.normalize(glm.cross(v1, v3))
				else:
					plane_target = plane_current

				# plane target is unit
				current_cross_target = glm.cross(plane_current, plane_target)

				cos_angle = glm.clamp(glm.dot(plane_current, plane_target), -1.0, 1.0)
				sin_angle = glm.dot(v1_unit, current_cross_target)  # triple product

				angle = glm.atan2(sin_angle, cos_angle)

				# guard when planes almost match
				if glm.length(current_cross_target) < 1e-6:
					angle = 0.0

				# add rotation so planes will match
				start_add_rot = glm.angleAxis(angle, v1_unit)
				start_new_rot = start_add_rot * start_rot

				# update start
				start_matrix = glm_compose_mat4(start_tr, start_new_rot, start_sc)
				# update dependent matrices
				target_matrix = start_matrix * target_offset_matrix
				target_sc, target_rot, target_tr = glm_decompose_mat4(target_matrix)

				end_constrained_matrix = target_matrix * end_offset_matrix
				end_constrained_tr = glm_get_translation(end_constrained_matrix)

				#  Law of Cosines
				upper_arm_len = glm.length(v1)
				forearm_len = glm.length(end_constrained_tr - target_tr)
				dist_to_target = glm.length(end_real_tr - start_tr)

				target_dist_clamped = glm.clamp(dist_to_target, abs(upper_arm_len - forearm_len), upper_arm_len + forearm_len)

				cos_shoulder_inner = glm.clamp(
					(upper_arm_len * upper_arm_len + target_dist_clamped * target_dist_clamped - forearm_len * forearm_len) /
					(2 * upper_arm_len * target_dist_clamped),
					-1,
					1
				)

				desired_shoulder_inner_angle: float = glm.acos(cos_shoulder_inner)

				cos_elbow_inner = glm.clamp(
					(upper_arm_len * upper_arm_len + forearm_len * forearm_len - target_dist_clamped * target_dist_clamped) /
					(2 * upper_arm_len * forearm_len),
					-1,
					1
				)
				desired_elbow_inner_angle = glm.acos(cos_elbow_inner)

				current_shoulder_to_elbow_vec = target_tr - start_tr

				# shoulder angle in plane
				current_shoulder_cross = glm.cross(current_shoulder_to_elbow_vec, v3)
				current_shoulder_angle = glm.atan2(glm.dot(current_shoulder_cross, plane_target), glm.dot(current_shoulder_to_elbow_vec, v3))

				target_shoulder_angle_signed = sign(current_shoulder_angle) * desired_shoulder_inner_angle
				shoulder_adjust_rot = glm.angleAxis((current_shoulder_angle - target_shoulder_angle_signed), plane_target)
				start_new_rot = shoulder_adjust_rot * start_new_rot  # reusing variable

				start_matrix = glm_compose_mat4(start_tr, start_new_rot, start_sc)
				skeleton_bones_matrices[start_bone_index] = start_matrix
				is_bone_updated[start_bone_index] = True

				# update target and end_constrained after moving start
				target_matrix = start_matrix * target_offset_matrix
				target_sc, target_rot, target_tr = glm_decompose_mat4(target_matrix)

				end_constrained_matrix = target_matrix * end_offset_matrix
				end_constrained_tr = glm_get_translation(end_constrained_matrix)

				# target angle in plane
				elbow_to_shoulder_vec = start_tr - target_tr
				elbow_to_hand_vec = end_constrained_tr - target_tr

				current_elbow_cross = glm.cross(elbow_to_shoulder_vec, elbow_to_hand_vec)
				current_elbow_angle = glm.atan2(glm.dot(current_elbow_cross, plane_target), glm.dot(elbow_to_shoulder_vec, elbow_to_hand_vec))

				target_elbow_angle_signed = sign(current_elbow_angle) * desired_elbow_inner_angle
				elbow_adjust_rot = glm.angleAxis((target_elbow_angle_signed - current_elbow_angle), plane_target)

				target_matrix = glm_compose_mat4(target_tr, elbow_adjust_rot * target_rot, target_sc)
				skeleton_bones_matrices[target_bone_index] = target_matrix
				is_bone_updated[target_bone_index] = True

		# store frame into converted animation
		for bone_index, updated in enumerate(is_bone_updated):
			if not updated:
				continue

			bone_matrix = skeleton_bones_matrices[bone_index]
			node_def = bones_relations[bone_index]
			parent_bone_index = node_def.parent_node_index

			sc, rot, tr = glm_decompose_mat4(bone_matrix)  # glm uses (w, x, y, z) quat order

			converted_animation[bone_index].scales[frame] = np.array([sc[0], sc[1], sc[2]])
			converted_animation[bone_index].rotations[frame] = np.array([rot[1], rot[2], rot[3], rot[0]])  # move w to last position
			converted_animation[bone_index].translations[frame] = np.array([tr[0], tr[1], tr[2]])


	end_time = time.perf_counter()
	logger.info(f"Retarget finished, time: {end_time-start_time:.6f}s")

	return converted_animation

import logging
import time
import numpy as np

from pyglm import glm

from matrix_operations.glm_matrix_operations import glm_compose_mat4, glm_decompose_mat4
from animation_decoding.decode_animation import Bone_Tracks
from tag_readers.read_animation import Animation_Data
from tag_readers.read_skeleton import Skeleton


logger = logging.getLogger(__name__)


def convert_obj_to_local(
	animation_data: Animation_Data,
	bones_data: list[Bone_Tracks],
	skeleton: Skeleton,
):
	frames = animation_data.animation_header.frame_count

	skeleton_node_defs = skeleton.node_defs
	num_bones = skeleton_node_defs.length
	skeleton_bones_matrices = glm.array.zeros(num_bones, glm.mat4)

	# pre-allocate data filled with identity values
	converted_animation = [
		Bone_Tracks(
			bone_name_hash=skeleton_node_defs[bone_index].bone_hash,
			scales=np.ones((frames, 3), dtype=np.float32),  # 1.0
			rotations=np.zeros((frames, 4), dtype=np.float32),  # [0,0,0,1]
			translations=np.zeros((frames, 3), dtype=np.float32)  # 0.0
		) for bone_index in range(num_bones)
	]

	for track in converted_animation:
		track.rotations[:, 3] = 1.0

	logger.info("Conversion started")
	start_time = time.perf_counter()

	for frame in range(frames):
		for bone_index in range(num_bones):
			sc = bones_data[bone_index].scales[frame]
			rot = bones_data[bone_index].rotations[frame]
			tr = bones_data[bone_index].translations[frame]

			bone_matrix = glm_compose_mat4(
				glm.vec3(tr),
				glm.quat(rot[3], rot[0], rot[1], rot[2]),
				glm.vec3(sc)
			)
			skeleton_bones_matrices[bone_index] = bone_matrix

			node_def = skeleton_node_defs[bone_index]
			parent_bone_index = node_def.parent_node_index

			if parent_bone_index > -1:
				parent_bone = skeleton_bones_matrices[parent_bone_index]
				bone_matrix = glm.inverse(parent_bone) * bone_matrix

			sc, rot, tr = glm_decompose_mat4(bone_matrix)

			converted_animation[bone_index].scales[frame] =  np.array([sc[0], sc[1], sc[2]])
			converted_animation[bone_index].rotations[frame] = np.array([rot[1], rot[2], rot[3], rot[0]]) # move w to last position
			converted_animation[bone_index].translations[frame] = np.array([tr[0], tr[1], tr[2]])

	end_time = time.perf_counter()
	logger.info(f"Conversion finished, time: {end_time-start_time:.6f}s")

	return converted_animation

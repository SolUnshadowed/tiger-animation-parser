# libs
import numpy as np
from scipy.spatial.transform import Slerp
from scipy.spatial.transform import Rotation as R

# custom
from type_read_functions import u32_to_le_hex
from numpy_matrix_operations import *
from console_progress_bar import Console_progress_bar

def calc_control_limit(rig, compatible_levels):
	print("Runtime rig subsets limit")
	limit = 0

	for i in range(compatible_levels):
		component = rig["components"][i]
		component_string_hash = u32_to_le_hex( component[0])
		print(f"\tuse subset [{i}], {component_string_hash}, control count: {component[1]}")
		limit += component[1]

	return limit


def rig_retarget(rig, compatible_levels, animation_data, bone_tracks, skeleton, mode="local"):
	frame = 0;
	frames = animation_data["frame_count"]

	bone_to_control = rig["bone_to_control"]
	control_to_bone = rig["control_to_bone"]
	constraints = rig["constraints"]

	reference_bones = []
	bone_to_bind_matrix = []
	bone_to_parent_offset = []

	transforms = skeleton['definition']['default_object_space_transforms']
	nodes = skeleton['definition']['nodes']

	# compute reference bone matrices
	for node_index, node in enumerate(nodes):
		SRTMatrix = make_srt_matrix(transforms[node_index])
		reference_bones.append(SRTMatrix)

	# compute bone to parent offsets
	for node_index, current_bone in enumerate(reference_bones):
		node = nodes[node_index]
		parent_index = node.get('parent_node_index', -1)

		if parent_index > -1:
			parent_bone = reference_bones[parent_index]
			offset_matrix = np.linalg.inv(parent_bone) @ current_bone
			bone_to_parent_offset.append(offset_matrix)
		else:
			bone_to_parent_offset.append(current_bone)

		bone_to_bind_matrix.append(current_bone.copy())

	# skeleton bones matrices
	num_bones = len(nodes)
	skeleton_bones_matrices = [make_identity() for _ in range(num_bones)]

	# bone controls matrices, limit by compatible layers
	controls_limit = calc_control_limit(rig, compatible_levels)

	print("Rig retarget // Info: Controls limit:", controls_limit)
	#num_controls = animation_data["rig_control_count"]

	bone_controls_matrices = [make_identity() for _ in range(controls_limit)]

	converted_animation = {}

	progress = Console_progress_bar(frames)
	print("Rig retarget // Info: Retarget started")

	for frame in range(frames):
		is_control_updated = [False for _ in range(len(bone_controls_matrices))]
		is_bone_updated = [False for _ in range(len(skeleton_bones_matrices))]

		for control_index in bone_tracks:

			if control_index >= controls_limit: # because not every index can be present in bone_tracks
				break

			bone_index = control_to_bone[control_index]
			track_group = bone_tracks[control_index]

			if len(track_group['scales']) == 0 and len(track_group['rotations']) == 0 and len(track_group['translations']) == 0:
				is_bone_updated[bone_index] = True
				continue

			scale = track_group['scales'][0] if len(track_group['scales']) == 1 else track_group['scales'][frame]
			rotation = track_group['rotations'][0] if len(track_group['rotations']) == 1 else track_group['rotations'][frame]
			translation = track_group['translations'][0] if len(track_group['translations']) == 1 else track_group['translations'][frame]

			if control_index in constraints:
				constraint = constraints[control_index]

				new_sc = [scale, scale, scale]
				new_rot = None
				new_tr = None

				# translation constraints
				animation_tr = np.array([translation[1], translation[2], translation[0]])

				ts_space = constraint['translation']['space']
				if ts_space == "object": # just copy animation translation
					new_tr = animation_tr

				elif ts_space == "bind": # animation tr + bind tr, for case when rotation is in object space!
					bind_matrix = bone_to_bind_matrix[bone_index]
					bind_tr = get_translation(bind_matrix)
					new_tr = bind_tr + animation_tr

				elif ts_space == "parent": # parent.tr + offset.tr + animation.tr
					parent_index = constraint['translation']['bone_index']

					if not is_bone_updated[parent_index]:
						print(f"tr constraint 'parent': bone {parent_index} is not updated yet!");
						continue

					parent_matrix = skeleton_bones_matrices[parent_index]

					parent_tr = get_translation(parent_matrix)
					parent_rot_mat = get_rotation_matrix(parent_matrix)

					offset_matrix = bone_to_parent_offset[bone_index]
					offset_tr = get_translation(offset_matrix)
					offset_rot_mat = get_rotation_matrix(offset_matrix)

					new_tr = parent_tr + parent_rot_mat @ (offset_tr + offset_rot_mat @ animation_tr)

				elif ts_space == "average": # for case when rotation is in object space!
					parent_1_index = constraint['translation']['bone_index_1']
					parent_2_index = constraint['translation']['bone_index_2']

					if not is_bone_updated[parent_1_index]:
						print(f"tr constraint 'average': bone {parent_1_index} is not updated yet!");
						continue

					if not is_bone_updated[parent_2_index]:
						print(f"tr constraint 'average': bone {parent_2_index} is not updated yet!");
						continue

					pos1 = get_translation(skeleton_bones_matrices[parent_1_index])
					pos2 = get_translation(skeleton_bones_matrices[parent_2_index])
					new_tr = animation_tr + 0.5 * (pos1 + pos2)

				elif ts_space == "relative": # basically if tr is local bone matrix
					parent_index = constraint['translation']['bone_index']

					if not is_bone_updated[parent_index]:
						print(f"tr constraint 'relative': bone {parent_index} is not updated yet!");
						continue

					parent_matrix = skeleton_bones_matrices[parent_index]
					parent_tr = get_translation(parent_matrix)
					parent_rot_mat = get_rotation_matrix(parent_matrix)
					new_tr = parent_tr + parent_rot_mat @ animation_tr

				elif ts_space == "relative2": # relative to some bone, and rotation is in object space
					parent_index = constraint['translation']['bone_index']

					if not is_bone_updated[parent_index]:
						print(f"tr constraint 'relative2': bone {parent_index} is not updated yet!");
						continue

					parent_matrix = skeleton_bones_matrices[parent_index]
					parent_tr = get_translation(parent_matrix)
					new_tr = animation_tr + parent_tr

				# rotation constraints
				rot_space = constraint['rotation']['space']
				animation_rot = R.from_quat([rotation[1], rotation[2], rotation[0], rotation[3]])

				if rot_space == "object": # just copy animation rotation
					new_rot = animation_rot

				elif rot_space == "parent": #
					parent_index = constraint['rotation']['bone_index']

					if not is_bone_updated[parent_index]:
						print(f"rot constraint 'parent': bone {parent_index} is not updated yet!");
						continue

					parent_matrix = skeleton_bones_matrices[parent_index]
					parent_rot = get_rotation(parent_matrix)

					offset_matrix = bone_to_parent_offset[bone_index]
					offset_rot = get_rotation(offset_matrix)

					new_rot = parent_rot * offset_rot * animation_rot

				elif rot_space == "relative":
					parent_index = constraint['rotation']['bone_index']

					if not is_bone_updated[parent_index]:
						print(f"rot constraint 'relative': bone {parent_index} is not updated yet!");
						continue

					parent_matrix = skeleton_bones_matrices[parent_index]
					parent_rot = get_rotation(parent_matrix)
					new_rot = parent_rot * animation_rot

				# compose final bone matrix
				bone_mat = compose_matrix(new_tr, new_rot, new_sc)
				skeleton_bones_matrices[bone_index] = bone_mat

				is_control_updated[control_index] = True
				is_bone_updated[bone_index] = True

				# RFK chain
				if 'rfk' in constraint:
					rfk_start = constraint['rfk']['bone_index']
					chain = [bone_index]
					curr = bone_index
					found_start = False

					while True:
						curr = nodes[curr]['parent_node_index']
						chain.append(curr)
						if curr == rfk_start:
							found_start = True
							break

					if found_start:
						chain = list(reversed(chain))
						start_bone_quat = get_rotation(skeleton_bones_matrices[chain[0]])

						if not is_bone_updated[chain[0]]:
							print(f"rfk function: start bone {chain[0]} is not updated yet!");
							continue

						end_bone_quat = get_rotation(skeleton_bones_matrices[chain[-1]])

						if not is_bone_updated[chain[-1]]:
							print(f"rfk function: end bone {chain[-1]} is not updated yet!");
							continue

						# difference between start and end
						difference_quat = start_bone_quat.inv() * end_bone_quat

						parent_mat = skeleton_bones_matrices[chain[0]]
						N = len(chain) # full chain length
						K = N - 2 # intermedaite bones (without start and end)

						# only for bones 1..N-2
						for i in range(1, K + 1):
							t = i / (N - 1) # t = 1/(K+1), 2/(K+1), ... K/(K+1)
							slerp = Slerp([0, 1], R.concatenate([R.identity(), difference_quat]))
							difference_quat_step = slerp([t])[0]  # slerp returns an array

							target_bone_index = chain[i]
							offset_mat = bone_to_parent_offset[target_bone_index]
							target_mat = parent_mat @ offset_mat
							target_tr = get_translation(target_mat)
							target_sc = get_scale(target_mat)
							target_rot = get_rotation(target_mat)
							target_new_rot = start_bone_quat * difference_quat_step

							new_mat = compose_matrix(target_tr, target_new_rot, target_sc)

							skeleton_bones_matrices[target_bone_index] = new_mat
							parent_mat = new_mat
							is_bone_updated[target_bone_index] = True

				# IK_3 chain
				if 'ik_3' in constraint:
					ik_start = constraint['ik_3']['bone_index']
					chain = [bone_index]
					curr = bone_index
					found_start = False

					while True:
						curr = nodes[curr]['parent_node_index']
						chain.append(curr)
						if curr == ik_start:
							found_start = True
							break

					if found_start and len(chain) == 3:
						end_bone_index, target_bone_index, start_bone_index = chain

						# select bones (not conrols as ik bones have no controls, in d1 at least)

						# start is already moved in right position
						start_mat = skeleton_bones_matrices[start_bone_index] # shoulder / thigh
						start_tr = get_translation(start_mat)
						start_rot = get_rotation(start_mat)
						start_sc = get_scale(start_mat)

						target_offset_mat = bone_to_parent_offset[target_bone_index]
						target_mat = start_mat @ target_offset_mat # elbow / knee <- the one being soved
						# extract target scale, rotation, translation [scale and translation are already good, need to change rotation, currently it is "default"]
						target_tr = get_translation(target_mat)
						target_rot = get_rotation(target_mat)
						target_sc = get_scale(target_mat)

						# end is already moved in right position
						end_mat = skeleton_bones_matrices[end_bone_index] # wrist / foot
						end_real_tr = get_translation(end_mat) # end
						# where end would be with current target_rot end'
						end_offset_mat = bone_to_parent_offset[end_bone_index]
						end_constrained_tr = get_translation(target_mat @ end_offset_mat)

						# add rotation to start
						v1 = normalize_vec(target_tr - start_tr) # shoulder -> elbow / thigh -> knee
						v2 = normalize_vec(end_constrained_tr - start_tr) #
						v3 = normalize_vec(end_real_tr - start_tr)

						# |v1 x v3| = sinA * |v1| * |v3|
						# |v1|, |v3| == 1
						# |v1 x v3| = sinA
						cross_check = np.linalg.norm(np.cross(v1, v3))

						# angle is checked in case if chain is fully extended
						# if it is fully extended there is no plane to match, so this block will not be executed
						if cross_check > 0.0872: # more than 5 deg, so it is bent
							# planes
							plane_current = normalize_vec(np.cross(v1, v2)) # plane with end not in right position
							plane_target = normalize_vec(np.cross(v1, v3)) # plane with end in right position
							current_cross_target = np.cross(plane_current, plane_target)

							# signed angle between planes
							cos_angle = np.clip(np.dot(plane_current, plane_target), -1.0, 1.0)
							sin_angle = np.dot(v1, current_cross_target)
							angle = np.arctan2(sin_angle, cos_angle)

							# guard when planes almost match
							if np.linalg.norm(current_cross_target) < 1e-6:
								angle = 0.0

							# add rotation so planes will match
							start_add_rot = R.from_rotvec(v1 * angle)
							start_new_rot = start_add_rot * start_rot

							# update start
							start_mat_new = compose_matrix(start_tr, start_new_rot, start_sc)
							skeleton_bones_matrices[start_bone_index] = start_mat_new
							is_bone_updated[start_bone_index] = True

							# after start was updated need to update target and end_constrained as they depend on start
							target_mat = start_mat_new @ target_offset_mat
							target_tr = get_translation(target_mat)
							target_rot = get_rotation(target_mat)
							target_sc = get_scale(target_mat)

							end_constrained_tr = get_translation(target_mat @ end_offset_mat)

						# now as rotation planes match, need to rotate target, so end would end up where it should be

						# plane normal by using bind pose [right now target in "bind" position, e.g. how elbow is bent as in bind pose]
						start_to_target = normalize_vec(target_tr - start_tr)
						start_to_end_constrained = normalize_vec(end_constrained_tr - start_tr)
						# three points (start, target', end') not on same line -> triangle -> triangle produces plane of rotation
						plane_normal = normalize_vec(np.cross(start_to_end_constrained, start_to_target))

						# find additional angle
						target_to_end_constrained = normalize_vec(end_constrained_tr - target_tr) # from target (knee/elbow) to unbent knee/elbow
						target_to_end_real = normalize_vec(end_real_tr - target_tr) # from target (knee/elbow) to bent knee/elbow

						# vector product shows the direction of rotation for correction
						cross = np.cross(target_to_end_constrained, target_to_end_real)

						# cosine of the angle between the unbent and real positions
						dot = np.clip(np.dot(target_to_end_constrained, target_to_end_real), -1.0, 1.0)

						# additional angle of rotation around the plane normal
						target_add_angle = np.arctan2(np.dot(cross, plane_normal), dot)

						# create quat in plane of rotation
						target_add_rot = R.from_rotvec(plane_normal * target_add_angle)
						target_new_rot = target_add_rot * target_rot

						# update target
						target_mat_new = compose_matrix(target_tr, target_new_rot, target_sc)
						skeleton_bones_matrices[target_bone_index] = target_mat_new
						is_bone_updated[target_bone_index] = True

		# store frame into converted animation
		for bone_index, updated in enumerate(is_bone_updated):
			if not updated:
				continue

			if bone_index not in converted_animation:
				converted_animation[bone_index] = {
					'bone_name_hash': nodes[bone_index]['name']["hash"],
					'scales': [],
					'rotations': [],
					'translations': []
				}

			bone_matrix = skeleton_bones_matrices[bone_index]
			node_def = nodes[bone_index]
			parent_index = node_def.get('parent_node_index', -1)

			transformed_matrix = bone_matrix

			# this produces local animation, if mode not local it will write world space matrices
			if parent_index > -1 and mode == "local":
				parent_bone = skeleton_bones_matrices[parent_index]
				transformed_matrix = np.linalg.inv(parent_bone) @ bone_matrix

			sc = get_scale(transformed_matrix)
			rot = get_rotation(transformed_matrix).as_quat()  # x,y,z,w
			tr = get_translation(transformed_matrix)

			converted_animation[bone_index]['scales'].append(sc.tolist())
			converted_animation[bone_index]['rotations'].append(rot.tolist())
			converted_animation[bone_index]['translations'].append(tr.tolist())

		progress.step()
	print("Rig retarget // Info: Retarget finished")

	return converted_animation

def transform_and_annotate_tracks(tracks, skeleton):
	# add bones names and change order of coords
	# rig just does it in process
	nodes = skeleton['definition']['nodes']

	for bone_index in tracks:
		track_group = tracks[bone_index]
		track_group['bone_name_hash'] = nodes[bone_index]['name']["hash"]

		for i in range(len(track_group["rotations"])):
			rot = track_group["rotations"][i]
			rot[0], rot[1], rot[2] = rot[1], rot[2], rot[0]

		for i in range(len(track_group["translations"])):
			tr = track_group["translations"][i]
			tr[0], tr[1], tr[2] = tr[1], tr[2], tr[0]

		for i in range(len(track_group["scales"])):
			sc = track_group["scales"][i]
			track_group["scales"][i] = [sc, sc, sc]

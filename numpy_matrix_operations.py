import numpy as np
from scipy.spatial.transform import Rotation as R

def make_srt_matrix(transform):
	scale = transform.get('ts', [0,0,0,1])[3] if len(transform.get('ts', [])) >= 4 else 1.0

	# rotation swap [x, y, z, w] -> [y, z, x, w]
	r = transform.get('r', [0,0,0,1])
	rotation = [r[1], r[2], r[0], r[3]]
	rot_obj = R.from_quat(rotation)  # Rotation

	# translation swap [x, y, z] -> [y, z, x]
	ts = transform.get('ts', [0,0,0,1])
	translation = [ts[1], ts[2], ts[0]]

	# compose matrix using helper
	matrix = compose_matrix(translation, rot_obj, [scale, scale, scale])

	return matrix

def make_identity():
	return np.eye(4)

def set_translation(matrix, translation):
	matrix[:3, 3] = np.array(translation)
	return matrix

def get_translation(matrix):
	return matrix[:3, 3].copy()

def set_rotation(matrix, rot: R):
	scale = get_scale(matrix)
	matrix[:3, :3] = rot.as_matrix() * scale.reshape(1,3)
	return matrix

def set_rotation_matrix(matrix, rot_matrix):
	scale = get_scale(matrix)
	matrix[:3, :3] = np.array(rot_matrix) * scale.reshape(1,3)
	return matrix

def get_rotation(matrix):
	scale = get_scale(matrix)
	rot_mat = matrix[:3, :3] / scale.reshape(1,3)
	return R.from_matrix(rot_mat)

def get_rotation_matrix(matrix):
	scale = get_scale(matrix)
	rot_mat = matrix[:3, :3] / scale.reshape(1,3)
	return rot_mat

def set_scale(matrix, scale):
	rot = get_rotation(matrix)
	matrix[:3, :3] = rot.as_matrix() * np.array(scale).reshape(1,3)
	return matrix

def get_scale(matrix):
	return np.linalg.norm(matrix[:3, :3], axis=0)

def compose_matrix(translation, rotation: R, scale):
	matrix = make_identity()
	set_scale(matrix, scale)
	set_rotation(matrix, rotation)
	set_translation(matrix, translation)
	return matrix

def decompose_matrix(matrix):
	translation = get_translation(matrix)
	scale = get_scale(matrix)
	rot = get_rotation(matrix)
	return translation, rot, scale

def normalize_vec(vector):
	norm = np.linalg.norm(vector)

	if norm == 0:
		return vector
	return vector / norm

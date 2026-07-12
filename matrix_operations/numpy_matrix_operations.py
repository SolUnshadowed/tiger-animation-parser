import numpy as np
from scipy.spatial.transform import Rotation as R


def np_make_identity():
	return np.eye(4)


def np_set_translation(matrix, translation):
	matrix[:3, 3] = translation
	return matrix


def np_get_translation(matrix):
	return matrix[:3, 3].copy()


def np_set_rotation(matrix, rot: R):
	scale = np_get_scale(matrix)
	matrix[:3, :3] = rot.as_matrix() * scale
	return matrix


def np_set_rotation_matrix(matrix, rot_matrix):
	scale = np_get_scale(matrix)
	matrix[:3, :3] = rot_matrix * scale
	return matrix


def np_get_rotation(matrix):
	scale = np_get_scale(matrix)
	return R.from_matrix(matrix[:3, :3] / scale, assume_valid=True)


def np_get_rotation_matrix(matrix):
	scale = np_get_scale(matrix)
	rot_mat = matrix[:3, :3] / scale
	return rot_mat


def np_set_scale(matrix, scale):
	rot = np_get_rotation(matrix)
	matrix[:3, :3] = rot.as_matrix() * scale
	return matrix


def np_get_scale(matrix):
	return np.linalg.norm(matrix[:3, :3], axis=0)


def np_compose_matrix(translation, rotation: R, scale):
	matrix = np.eye(4, dtype=translation.dtype)
	matrix[:3, :3] = rotation.as_matrix() * scale
	matrix[:3, 3] = translation
	return matrix


def np_decompose_matrix(mat):
	return np_get_scale(mat), np_get_rotation(mat), np_get_translation(mat)


def np_normalize_vec(vector):
	norm = np.linalg.norm(vector)
	if norm == 0:
		return vector
	return vector / norm

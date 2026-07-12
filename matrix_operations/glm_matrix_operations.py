from pyglm import glm


def glm_get_scale(mat: glm.mat4):
	return glm.vec3(
		glm.length(glm.vec3(mat[0])),
		glm.length(glm.vec3(mat[1])),
		glm.length(glm.vec3(mat[2]))
	)

def glm_get_quat(mat: glm.mat4):
	scale = glm_get_scale(mat)
	pure_rot_mat = glm.mat4(mat)

	pure_rot_mat[0] /= (scale.x if scale.x > 0.00001 else 1.0)
	pure_rot_mat[1] /= (scale.y if scale.y > 0.00001 else 1.0)
	pure_rot_mat[2] /= (scale.z if scale.z > 0.00001 else 1.0)

	return glm.normalize(glm.quat_cast(pure_rot_mat))


def glm_get_translation(mat: glm.mat4):
	return glm.vec3(mat[3])


def glm_set_translation(mat: glm.mat4, translation: glm.vec3):
	mat[3].xyz = translation


def glm_set_quat(mat: glm.mat4, rotation: glm.quat):
	scale = glm_get_scale(mat)
	rot_mat3 = glm.mat3_cast(rotation)

	mat[0].xyz = rot_mat3[0] * scale.x
	mat[1].xyz = rot_mat3[1] * scale.y
	mat[2].xyz = rot_mat3[2] * scale.z


def glm_set_scale(mat: glm.mat4, scale: glm.vec3):
	current_scale = glm_get_scale(mat)

	mat[0].xyz = (mat[0].xyz / (current_scale.x if current_scale.x > 0.00001 else 1.0)) * scale.x
	mat[1].xyz = (mat[1].xyz / (current_scale.y if current_scale.y > 0.00001 else 1.0)) * scale.y
	mat[2].xyz = (mat[2].xyz / (current_scale.z if current_scale.z > 0.00001 else 1.0)) * scale.z


def glm_compose_mat4(translation: glm.vec3, rotation: glm.quat, scale: glm.vec3):
	mat = glm.mat4(1.0)
	rot_mat3 = glm.mat3_cast(rotation)

	mat[0].xyz = rot_mat3[0] * scale.x
	mat[1].xyz = rot_mat3[1] * scale.y
	mat[2].xyz = rot_mat3[2] * scale.z
	mat[3].xyz = translation

	return mat


def glm_compose_mat4_inplace(out_mat: glm.mat4, translation: glm.vec3, rotation: glm.quat, scale: glm.vec3):
	rot_mat3 = glm.mat3_cast(rotation)

	# set scale and rotation
	out_mat[0].xyz = rot_mat3[0] * scale.x
	out_mat[1].xyz = rot_mat3[1] * scale.y
	out_mat[2].xyz = rot_mat3[2] * scale.z

	# set position
	out_mat[3].xyz = translation

	# clean?
	out_mat[0].w = 0.0
	out_mat[1].w = 0.0
	out_mat[2].w = 0.0
	out_mat[3].w = 1.0


def glm_decompose_mat4(mat: glm.mat4):
	scale = glm_get_scale(mat)

	pure_rot_mat = glm.mat4(mat)

	pure_rot_mat[0] /= (scale.x if scale.x > 0.00001 else 1.0)
	pure_rot_mat[1] /= (scale.y if scale.y > 0.00001 else 1.0)
	pure_rot_mat[2] /= (scale.z if scale.z > 0.00001 else 1.0)

	rotation = glm.normalize(glm.quat_cast(pure_rot_mat))
	translation = glm_get_translation(mat)

	return scale, rotation, translation

import base64
import logging
import numpy as np
from pygltflib import (
	GLTF2, Node, Animation, AnimationChannel, AnimationSampler,
	Buffer, BufferView, Accessor, FLOAT,
	TRANSLATION, ROTATION, SCALE, Scene, Skin, AnimationChannelTarget
)

from .enums import Name_Convention, Animation_Space
from matrix_operations.numpy_matrix_operations import np_decompose_matrix
from tag_readers.read_skeleton import transform_to_np_matrix
from tag_readers.read_skeleton import Skeleton
from fnv_hashes.int_to_hex import u32_to_le_hex, u32_to_be_hex
from fnv_hashes.bones_names import convert_hash_to_blender_name, convert_hash_to_bungie_name
from animation_decoding.decode_animation import Bone_Tracks


logger = logging.getLogger(__name__)


def get_bone_name(num, convention: Name_Convention):
	match convention:
		case Name_Convention.FNV1LE:
			return u32_to_le_hex(num)
		case Name_Convention.FNV1LE_NO_ZEROES:
			return u32_to_le_hex(num).lstrip('0')
		case Name_Convention.FNV1BE:
			return u32_to_be_hex(num)
		case Name_Convention.FNV1BE_NO_ZEROES:
			return u32_to_be_hex(num).lstrip('0')
		case Name_Convention.BLENDER:
			return convert_hash_to_blender_name(num)
		case Name_Convention.BUNGIE:
			return convert_hash_to_bungie_name(num)
		case _:
			return u32_to_be_hex(num)


def pack_buffer_entries(gltf, entries, target=None):
	"""
	Packs all entries of entries array into one Buffer and creates BufferView + Accessor for each
	entries: [
		{
			'name': str,          # name
			'type': str,          # 'SCALAR', 'VEC3', 'VEC4', 'MAT4'
			'data': np.array      # numpy array
		}
	]
	target: target for BufferView.

	returns indices of accessors in the same order as entries
	accessor[i] for entriies[i]
	"""
	accessor_indices = []
	buffer_bytes = bytearray()
	buffer_index = len(gltf.buffers)

	for entry in entries:
		data = entry["data"]
		dtype = entry["type"]

		# align by four bytes
		while len(buffer_bytes) % 4 != 0:
			buffer_bytes.append(0)
		offset = len(buffer_bytes)

		data_bytes = data.astype("<f4").tobytes()
		buffer_bytes += data_bytes

		# BufferView
		buffer_view = BufferView(
			buffer=buffer_index,
			byteOffset=offset,
			byteLength=len(data_bytes),
			target=target  # None for inverse bind matrices animation
		)

		# save index for accessor
		buffer_view_index = len(gltf.bufferViews)
		gltf.bufferViews.append(buffer_view)

		# Accessor
		if data.ndim == 1:
			accessor_type = "SCALAR"
			count = data.shape[0]
		elif data.ndim == 2:
			accessor_type = "VEC4" if data.shape[1] == 4 else "VEC3"
			count = data.shape[0]
		elif data.ndim == 3 and dtype == "MAT4":
			accessor_type = "MAT4"
			count = data.shape[0]
		else:
			raise ValueError(f"Unsupported data shape {data.shape} for accessor {entry['name']}")

		accessor = Accessor(
			bufferView=buffer_view_index,
			byteOffset=0,
			componentType=FLOAT,
			count=count,
			type=accessor_type
		)

		# for Input Accessor (SCALAR, times) add min/max
		if accessor_type == "SCALAR":
			accessor.min = [float(np.min(data))]
			accessor.max = [float(np.max(data))]

		accessor_index = len(gltf.accessors)
		gltf.accessors.append(accessor)
		accessor_indices.append(accessor_index)

	# Add buffer
	byte_length = len(buffer_bytes)
	b64_data = base64.b64encode(buffer_bytes).decode("utf-8")
	gltf.buffers.append(Buffer(byteLength=byte_length, uri=f"data:application/octet-stream;base64,{b64_data}"))

	return accessor_indices


def create_armature_object_space(
	gltf,
	skeleton_data: Skeleton,
	convention: Name_Convention
):
	"""
	Create armature nodes + fake root and skin with inverseBindMatrices.
	skeleton_json: destiny_player_skeleton.js
	"""
	nodes_data = skeleton_data.node_defs
	transforms = skeleton_data.default_obj_space_tr
	inv_transforms = skeleton_data.default_inv_obj_space_tr

	# Create fake root
	fake_root_node = Node(
		name="FakeRoot",
		children=[],
		translation=[0, 0, 0],
		rotation=[0, 0, 0, 1],
		scale=[1, 1, 1]
	)

	gltf.nodes.append(fake_root_node)
	fake_root_index = 0
	bone_indices = {}

	# Create real bones' nodes
	for i, node in enumerate(nodes_data):
		srt = transform_to_np_matrix(transforms[i])
		sc, rot, tr = np_decompose_matrix(srt)

		node_obj = Node(
			name=get_bone_name(node.bone_hash, convention),  # game name
			children=[],
			translation=tr.tolist(),
			rotation=rot.as_quat().tolist(),  # x,y,z,w
			scale=sc.tolist()
		)

		bone_index = len(gltf.nodes)
		gltf.nodes.append(node_obj)
		bone_indices[node_obj.name] = bone_index
		fake_root_node.children.append(bone_index)

	# Skin with inverseBindMatrices
	inv_bind_mat_list = []
	for transform in inv_transforms:
		mat = transform_to_np_matrix(transform)
		inv_bind_mat_list.append(np.array(mat.T, dtype=np.float32))  # glTF column-major

	inv_bind_mat_array = np.stack(inv_bind_mat_list, axis=0)  # shape = (num_bones, 4, 4)

	# pack with helper
	skin_entry = [{"name": "inverseBindMatrices", "type": "MAT4", "data": inv_bind_mat_array}]
	inv_bind_mat_accessor_index = pack_buffer_entries(gltf, skin_entry)[0]  # only one entry

	# Skin object
	skin = Skin(
		joints=[
			bone_indices[get_bone_name(n.bone_hash, convention)] for n in nodes_data
		],
		inverseBindMatrices=inv_bind_mat_accessor_index,
		skeleton=fake_root_index
	)

	gltf.skins.append(skin)

	logger.info("Created armature and skin")

	return fake_root_index, bone_indices


def create_armature_hierarchy(
	gltf,
	skeleton_data: Skeleton,
	convention: Name_Convention
):
	"""
	Create armature nodes with hierarchy and skin.
	Converts world-space transforms to local-space.
	"""
	nodes_data = skeleton_data.node_defs
	transforms = skeleton_data.default_obj_space_tr
	inv_transforms = skeleton_data.default_inv_obj_space_tr

	bone_indices = {}
	world_mats = [transform_to_np_matrix(t) for t in transforms]
	inv_world_mats = [transform_to_np_matrix(t) for t in inv_transforms]
	local_mats = []

	# conversion to local space
	for i, node in enumerate(nodes_data):

		parent_index = node.parent_node_index

		if parent_index >= 0:
			parent_inv_world = inv_world_mats[parent_index]
			child_world = world_mats[i]

			local = parent_inv_world @ child_world
		else:
			local = world_mats[i]

		local_mats.append(local)

	bone_indices = {}  # bone_name to index
	for i, node in enumerate(nodes_data):
		mat = local_mats[i]

		sc, rot, tr = np_decompose_matrix(mat)

		node_obj = Node(
			name=get_bone_name(node.bone_hash, convention),
			translation=tr.tolist(),
			rotation=rot.as_quat().tolist(),
			scale=sc.tolist()
		)

		index = len(gltf.nodes)
		gltf.nodes.append(node_obj)
		bone_indices[node_obj.name] = index

	# Create fake root
	fake_root_node = Node(
		name="Skeleton",
		children=[],
		translation=[0, 0, 0],
		rotation=[0, 0, 0, 1],
		scale=[1, 1, 1]
	)

	fake_root_index = len(gltf.nodes)
	gltf.nodes.append(fake_root_node)

	# build hierarchy
	for _, node in enumerate(nodes_data):
		node_name = get_bone_name(node.bone_hash, convention)
		child_index = bone_indices[node_name]
		parent_index = node.parent_node_index

		if parent_index > -1:
			parent_name = get_bone_name(nodes_data[parent_index].bone_hash, convention)
			parent_index = bone_indices[parent_name]
			gltf.nodes[parent_index].children.append(child_index)
		else:
			gltf.nodes[fake_root_index].children.append(child_index)

	# inverse bind matrices for skinning
	inv_bind_list = []

	for mat_json in inv_transforms:
		mat = transform_to_np_matrix(mat_json)
		inv_bind_list.append(np.array(mat.T, dtype=np.float32))

	inv_bind_array = np.stack(inv_bind_list, axis=0)

	entries = [{
		"name": "inverseBindMatrices",
		"type": "MAT4",
		"data": inv_bind_array
	}]

	inv_bind_mat_accessor = pack_buffer_entries(gltf, entries)[0]

	joints = [bone_indices[get_bone_name(n.bone_hash, convention)] for n in nodes_data]

	skin = Skin(
		joints=joints,
		inverseBindMatrices=inv_bind_mat_accessor,
		skeleton=fake_root_index
	)

	gltf.skins.append(skin)

	logger.info("Created hierarchical armature and skin")

	return fake_root_index, bone_indices


def add_animation(
	gltf,
	bone_indices,
	animation_data: list[Bone_Tracks],
	convention: Name_Convention,
	fps=30
):
	# bone_indices: dict bone_name -> bone_index
	anim_entries = []

	logger.info("Creating animation tracks")

	# Make entry for each bone
	for bone_index in range(len(animation_data)):
		data = animation_data[bone_index]
		bone_name = get_bone_name(data.bone_name_hash, convention)

		if bone_name not in bone_indices:
			continue

		tr_frames = len(data.translations)
		rot_frames = len(data.rotations)
		sc_frames = len(data.scales)

		if tr_frames == 0 and rot_frames == 0 and sc_frames == 0:
			continue

		tr_times = np.arange(0, tr_frames, dtype=np.float32) / fps
		rot_times = np.arange(0, rot_frames, dtype=np.float32) / fps
		sc_times = np.arange(0, sc_frames, dtype=np.float32) / fps

		# create separate tracks
		rotations = data.rotations
		translations = data.translations
		scales = data.scales

		# Add entry
		anim_entries.append({"name": f"{bone_name}_time_translation", 	"type": "SCALAR", 	"data": tr_times})
		anim_entries.append({"name": f"{bone_name}_translation", 		"type": "VEC3", 	"data": translations})
		anim_entries.append({"name": f"{bone_name}_time_rotation", 		"type": "SCALAR", 	"data": rot_times})
		anim_entries.append({"name": f"{bone_name}_rotation", 			"type": "VEC4", 	"data": rotations})
		anim_entries.append({"name": f"{bone_name}_time_scale", 		"type": "SCALAR", 	"data": sc_times})
		anim_entries.append({"name": f"{bone_name}_scale", 				"type": "VEC3", 	"data": scales})

	if not anim_entries:
		return

	logger.info("Animation tracks created")

	# pack all entries into single buffer
	accessor_indices = pack_buffer_entries(gltf, anim_entries)  # None for animation

	# create channels
	channels = []
	samplers = []
	index = 0

	logger.info("Adding samplers and accessors")

	for bone_index in range(len(animation_data)):
		data = animation_data[bone_index]
		bone_name = get_bone_name(data.bone_name_hash, convention)

		if bone_name not in bone_indices:
			continue

		tr_frames = len(data.translations)
		rot_frames = len(data.rotations)
		sc_frames = len(data.scales)

		if tr_frames == 0 and rot_frames == 0 and sc_frames == 0:
			continue

		node_index = bone_indices[bone_name]
		# Each bone has 6 accessors in order: time_tr, tr, time_rot, rot, time_sc, sc
		# and as we added them in this order we can just take indices
		time_tr = accessor_indices[index]
		index += 1

		tr_acc = accessor_indices[index]
		index += 1

		time_rot = accessor_indices[index]
		index += 1

		rot_acc = accessor_indices[index]
		index += 1

		time_sc = accessor_indices[index]
		index += 1

		sc_acc = accessor_indices[index]
		index += 1

		# Translation sampler + channel
		samplers.append(AnimationSampler(input=time_tr, output=tr_acc, interpolation="LINEAR"))
		channels.append(
			AnimationChannel(
				sampler=len(samplers) - 1,
				target=AnimationChannelTarget(node=node_index, path=TRANSLATION)
			)
		)

		# Rotation sampler + channel
		samplers.append(AnimationSampler(input=time_rot, output=rot_acc, interpolation="LINEAR"))
		channels.append(
			AnimationChannel(
				sampler=len(samplers) - 1,
				target=AnimationChannelTarget(node=node_index, path=ROTATION)
			)
		)

		# Scale sampler + channel
		samplers.append(AnimationSampler(input=time_sc, output=sc_acc, interpolation="LINEAR"))
		channels.append(
			AnimationChannel(
				sampler=len(samplers) - 1,
				target=AnimationChannelTarget(node=node_index, path=SCALE)
			)
		)

	logger.info("Samplers and accessors added")

	# add animation to gltf
	gltf.animations.append(Animation(
		name="MainAnim",
		channels=channels,
		samplers=samplers
	))

	logger.info("Added animation")


def export_gltf(
	skeleton_data: Skeleton,
	animation_data: list[Bone_Tracks],
	mode: Animation_Space,
	output_path: str,
	name_convention: Name_Convention
):
	gltf = GLTF2()
	gltf.nodes = []
	gltf.buffers = []
	gltf.bufferViews = []
	gltf.accessors = []
	gltf.animations = []
	gltf.skins = []

	if mode == Animation_Space.OBJECT:
		root_index, bone_indices = create_armature_object_space(gltf, skeleton_data, name_convention)
		gltf.scene = 0
		gltf.scenes = [Scene(nodes=[root_index])]

		add_animation(gltf, bone_indices, animation_data, name_convention, fps=30)
	elif mode == Animation_Space.LOCAL:
		root_index, bone_indices = create_armature_hierarchy(gltf, skeleton_data, name_convention)
		gltf.scene = 0
		gltf.scenes = [Scene(nodes=[root_index])]

		add_animation(gltf, bone_indices, animation_data, name_convention, fps=30)

	gltf.save(output_path)
	logger.info(f"Saved file as: {output_path}")

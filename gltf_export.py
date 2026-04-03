import json
import base64
import numpy as np
import mathutils
from pygltflib import (
	GLTF2, Node, Animation, AnimationChannel, AnimationSampler,
	Buffer, BufferView, Accessor, ARRAY_BUFFER, FLOAT,
	TRANSLATION, ROTATION, SCALE, Scene, Skin
)

from bone_names_conversion import game_to_blender_name
from console_progress_bar import Console_progress_bar

def make_srt_matrix(transform): # api skeleton have swapped axises
	ts = transform.get('ts', [0,0,0,1])
	r = transform.get('r', [0,0,0,1])
	scale = ts[3] if len(ts) > 3 else 1.0

	translation = mathutils.Vector([ts[1], ts[2], ts[0]])
	rotation = mathutils.Quaternion([r[3], r[1], r[2], r[0]])
	mat = mathutils.Matrix.Translation(translation) @ rotation.to_matrix().to_4x4() @ mathutils.Matrix.Diagonal((scale, scale, scale, 1))
	return mat

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

def create_armature_fake_worldspace(gltf, skeleton_json):
	"""
	Create armature nodes + fake root and skin with inverseBindMatrices.
	skeleton_json: destiny_player_skeleton.js
	"""
	nodes_data = skeleton_json['definition']['nodes']
	transforms = skeleton_json['definition']['default_object_space_transforms']
	inv_transforms = skeleton_json['definition']['default_inverse_object_space_transforms']

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
		srt = make_srt_matrix(transforms[i])
		tr, rot, sc = srt.to_translation(), srt.to_quaternion(), srt.to_scale()

		node_obj = Node(
			name = game_to_blender_name(node['name']['hash']), # game name
			children = [],
			translation = [tr.x, tr.y, tr.z],
			rotation = [rot.x, rot.y, rot.z, rot.w],  # x,y,z,w
			scale = [sc.x, sc.y, sc.z]
		)

		bone_index = len(gltf.nodes)
		gltf.nodes.append(node_obj)
		bone_indices[node_obj.name] = bone_index
		fake_root_node.children.append(bone_index)

	# Skin with inverseBindMatrices
	inv_bind_mat_list = []
	for mat_json in inv_transforms:
		mat = make_srt_matrix(mat_json)
		inv_bind_mat_list.append(np.array(mat.transposed(), dtype=np.float32))  # glTF column-major

	inv_bind_mat_array = np.stack(inv_bind_mat_list, axis=0)  # shape = (num_bones, 4, 4)

	# pack with helper
	skin_entry = [{"name": "inverseBindMatrices", "type": "MAT4", "data": inv_bind_mat_array}]
	inv_bind_mat_accessor_index = pack_buffer_entries(gltf, skin_entry)[0] # only one entry

	# Skin object
	skin = Skin(
		joints=[bone_indices[game_to_blender_name(n['name']['hash'])] for n in nodes_data],
		inverseBindMatrices=inv_bind_mat_accessor_index,
		skeleton=fake_root_index
	)

	gltf.skins.append(skin)

	print("GLTF export // Info: Created armature and skin")

	return fake_root_index, bone_indices

def create_armature_hierarchy(gltf, skeleton_json):
	"""
	Create armature nodes with hierarchy and skin.
	Converts world-space transforms to local-space.
	"""
	nodes_data = skeleton_json['definition']['nodes']
	transforms = skeleton_json['definition']['default_object_space_transforms']
	inv_transforms = skeleton_json['definition']['default_inverse_object_space_transforms']

	bone_indices = {}
	world_mats = []
	local_mats = []

	# world mats
	for t in transforms:
		world_mats.append(make_srt_matrix(t))

	# conversion to local space
	for i, node in enumerate(nodes_data):

		parent = node["parent_node_index"]

		if parent >= 0:
			parent_world = world_mats[parent]
			child_world = world_mats[i]

			local = parent_world.inverted() @ child_world
		else:
			local = world_mats[i]

		local_mats.append(local)

	bone_indices = {}
	for i, node in enumerate(nodes_data):
		mat = local_mats[i]

		tr = mat.to_translation()
		rot = mat.to_quaternion()
		sc = mat.to_scale()

		node_obj = Node(
			name=game_to_blender_name(node['name']['hash']),
			translation=[tr.x, tr.y, tr.z],
			rotation=[rot.x, rot.y, rot.z, rot.w],
			scale=[sc.x, sc.y, sc.z]
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
	for i, node in enumerate(nodes_data):
		child_idx = bone_indices[game_to_blender_name(node['name']['hash'])]
		parent = node["parent_node_index"]

		if parent > -1:
			parent_name = game_to_blender_name(nodes_data[parent]['name']['hash'])
			parent_idx = bone_indices[parent_name]
			gltf.nodes[parent_idx].children.append(child_idx)
		else:
			gltf.nodes[fake_root_index].children.append(child_idx)

	# inverse bind matrices for skinning
	inv_bind_list = []

	for mat_json in inv_transforms:
		mat = make_srt_matrix(mat_json)
		inv_bind_list.append(np.array(mat.transposed(), dtype=np.float32))

	inv_bind_array = np.stack(inv_bind_list, axis=0)

	entries = [{
		"name": "inverseBindMatrices",
		"type": "MAT4",
		"data": inv_bind_array
	}]

	inv_bind_mat_accessor = pack_buffer_entries(gltf, entries)[0]

	joints = [bone_indices[game_to_blender_name(n['name']['hash'])] for n in nodes_data]

	skin = Skin(
		joints=joints,
		inverseBindMatrices=inv_bind_mat_accessor,
		skeleton=0
	)

	gltf.skins.append(skin)

	print("GLTF export // Info: Created hierarchical armature and skin")

	return fake_root_index, bone_indices

def normalize_scale(s):
	# number -> to list
	if isinstance(s, (int, float)):
		return [s, s, s]

	# tuple -> list
	if isinstance(s, (list, tuple)):
		if len(s) == 3:
			return s
		elif len(s) == 1:
			return [s[0], s[0], s[0]]

	# fallback
	return [1.0, 1.0, 1.0]

def add_animation(gltf, bone_indices, animation_json, fps=30):
	#bone_indices: dict bone_name -> bone_index
	anim_entries = []

	progress = Console_progress_bar(len(animation_json))

	print("GLTF export // Info: Creating animation tracks")

	# Make entry for each bone
	for bone_index in animation_json:
		data = animation_json[bone_index]
		bone_name = game_to_blender_name(data["bone_name_hash"])

		if bone_name not in bone_indices:
			progress.step()
			continue

		#node_index = bone_indices[bone_name]
		tr_frames = len(data['translations'])
		rot_frames = len(data['rotations'])
		sc_frames = len(data['scales'])

		tr_times = np.array( [ i/fps for i in range(tr_frames)  ], dtype=np.float32)
		rot_times = np.array([ i/fps for i in range(rot_frames) ], dtype=np.float32)
		sc_times = np.array( [ i/fps for i in range(sc_frames)  ], dtype=np.float32)

		# create separate tracks
		rotations = np.array([[q[0], q[1], q[2], q[3]] for q in data['rotations']], dtype=np.float32)
		translations = np.array(data['translations'], dtype=np.float32)
		scales = np.array([normalize_scale(s) for s in data['scales']], dtype=np.float32)

		# Add entry
		anim_entries.append({"name": f"{bone_name}_time_translation", 	"type": "SCALAR", 	"data": tr_times})
		anim_entries.append({"name": f"{bone_name}_translation", 		"type": "VEC3", 	"data": translations})
		anim_entries.append({"name": f"{bone_name}_time_rotation", 		"type": "SCALAR", 	"data": rot_times})
		anim_entries.append({"name": f"{bone_name}_rotation", 			"type": "VEC4", 	"data": rotations})
		anim_entries.append({"name": f"{bone_name}_time_scale", 		"type": "SCALAR", 	"data": sc_times})
		anim_entries.append({"name": f"{bone_name}_scale", 				"type": "VEC3", 	"data": scales})

		progress.step()

	if not anim_entries:
		return

	print("GLTF export // Info: Animation tracks created")

	# pack all entries into single buffer
	accessor_indices = pack_buffer_entries(gltf, anim_entries) # None for animation

	# create channels
	channels = []
	samplers = []
	index = 0

	progress.reset()
	print("GLTF export // Info: Adding samplers and accessors")

	for bone_index in animation_json:
		data = animation_json[bone_index]
		bone_name = game_to_blender_name(data["bone_name_hash"])

		if bone_name not in bone_indices:
			progress.step()
			continue

		node_index = bone_indices[bone_name]
		# Each bone has 6 accessors in order: time_tr, tr, time_rot, rot, time_sc, sc
		# and as we added them in this order we can just take indices
		time_tr = accessor_indices[index]; index += 1
		tr_acc = accessor_indices[index]; index += 1
		time_rot = accessor_indices[index]; index += 1
		rot_acc = accessor_indices[index]; index += 1
		time_sc = accessor_indices[index]; index += 1
		sc_acc = accessor_indices[index]; index += 1

		# Translation sampler + channel
		samplers.append(AnimationSampler(input=time_tr, output=tr_acc, interpolation="LINEAR"))
		channels.append(AnimationChannel(sampler=len(samplers)-1, target={"node": node_index, "path": TRANSLATION}))

		# Rotation sampler + channel
		samplers.append(AnimationSampler(input=time_rot, output=rot_acc, interpolation="LINEAR"))
		channels.append(AnimationChannel(sampler=len(samplers)-1, target={"node": node_index, "path": ROTATION}))

		# Scale sampler + channel
		samplers.append(AnimationSampler(input=time_sc, output=sc_acc, interpolation="LINEAR"))
		channels.append(AnimationChannel(sampler=len(samplers)-1, target={"node": node_index, "path": SCALE}))

		progress.step()

	print("GLTF export // Info: Samplers and accessors added")

	# add animation to gltf
	gltf.animations.append(Animation(
		name="MainAnim",
		channels=channels,
		samplers=samplers
	))

	print("GLTF export // Info: Added animation")

def export_gltf(skeleton_json, animation_json, mode="local", output_path="out.gltf"):
	gltf = GLTF2()
	gltf.scene = 0
	gltf.scenes = [Scene(nodes=[0])]
	gltf.nodes = []
	gltf.buffers = []
	gltf.bufferViews = []
	gltf.accessors = []
	gltf.animations = []
	gltf.skins = []

	if mode == "world":
		root_index, bone_indices = create_armature_fake_worldspace(gltf, skeleton_json)
		add_animation(gltf, bone_indices, animation_json, fps=30)
	elif mode == "local":
		root_index, bone_indices = create_armature_hierarchy(gltf, skeleton_json)
		add_animation(gltf, bone_indices, animation_json, fps=30)

	gltf.save(output_path)
	print("GLTF export // Info: Saved file as:", output_path)

from type_read_functions import u32_to_le_hex
from enums import Game_version, Rig_types
from constraints import *
from bone_mappings import *

def compare_rig_components_to_known_rig(rig, components):
	if len(rig["components"]) != len(components): # amount of components should match
		return False

	components_match = True
	components_sum = 0

	for i in range(len(components)):
		ref_component = rig["components"][i]
		test_component = u32_to_le_hex(components[i][0])

		components_sum += components[i][1]

		components_match = components_match & (ref_component == test_component)

	return (
		components_match and # components should be the same
		components_sum == rig["rig_control_count"] # and bones they add should match rig_control_count
	)

def find_compatible_rig(animation_rig_components, game_version):
	if game_version not in rigs:
		return None, 0

	rig_list = rigs[game_version]

	for rig in rig_list:
		rig_components = rig["components"]

		min_length = min(len(rig_components), len(animation_rig_components))

		levels_compatible = 0
		for i in range(min_length):
			animation_rig_level_hash, animation_rig_control_count = animation_rig_components[i]
			rig_level_hash, rig_control_count = rig_components[i]

			if animation_rig_level_hash != rig_level_hash or animation_rig_control_count != rig_control_count: # if even one does not match
				break

			levels_compatible += 1

		if levels_compatible > 0:
			return rig, levels_compatible

	return None, 0



destiny_player_cinematic_rig = {
	"type": Rig_types.CINEMATIC,
	"components": [
		[1662065363, 72] # D31A1163
	],
	"rig_control_count": 72
}

# pre-BL
destiny_pre_bl_player_runtime_rig = {
	"type": Rig_types.RUNTIME,
	"components": [
		[4291441111, 19], # D731CAFF
		[3329244285, 30], # 7D3C70C6
		[4142012067, 9],  # A316E2F6
		[2559375589, 8]   # E5F88C98
	],
	"rig_control_count": 66,
	"constraints": {
		**destiny_common_player_runtime_rig_layer_0_constraints,
		**destiny_common_player_runtime_rig_layer_1_constraints,
		**destiny_common_player_runtime_rig_layer_2_constraints,
		**destiny_pre_bl_player_runtime_rig_layer_3_constraints
	},
	"bone_to_control": bone_to_control_pre_bl,
	"control_to_bone": contol_to_bone_pre_bl
}

destiny_post_bl_player_runtime_rig = {
	"type": Rig_types.RUNTIME,
	"components": [
		[4291441111, 19], # D731CAFF
		[3329244285, 30], # 7D3C70C6
		[4142012067, 9],  # A316E2F6
		[2559375589, 14]   # E5F88C98
	],
	"rig_control_count": 72,
	"constraints": {
		**destiny_common_player_runtime_rig_layer_0_constraints,
		**destiny_common_player_runtime_rig_layer_1_constraints,
		**destiny_common_player_runtime_rig_layer_2_constraints,
		**destiny_post_bl_player_runtime_rig_layer_3_constraints
	},
	"bone_to_control": bone_to_control_post_bl,
	"control_to_bone": contol_to_bone_post_bl
}

rigs = {
	Game_version.D1_ROI: [
		destiny_player_cinematic_rig,
		destiny_pre_bl_player_runtime_rig
	],
	Game_version.D2_SK: [
		destiny_player_cinematic_rig,
		destiny_pre_bl_player_runtime_rig
	],
	Game_version.D2_EOF: [
		destiny_player_cinematic_rig,
		destiny_post_bl_player_runtime_rig
	]
}

import sys
import json

from enums import Game_version, Player_runtime_rig_version, Rig_types, Export_target

from known_rigs import find_compatible_rig
from rig_retarget import rig_retarget, transform_and_annotate_tracks
from gltf_export import export_gltf

game_version_to_rig_runtime_version = {
	Game_version.D1_ROI: Player_runtime_rig_version.D1,
	Game_version.D2_SK: Player_runtime_rig_version.D1,
	Game_version.D2_EOF: Player_runtime_rig_version.D2,
}

def compose_result_animation(animation_data, bone_data):
	result = [
		{
			"bone_tracks": bone_data,
			"frame_count": animation_data["frame_count"],
			"node_count": animation_data["node_count"],
			"rig_control_count": animation_data["rig_control_count"],
			"static_codec_type": animation_data["static_codec_type"],
			"animated_codec_type": animation_data["animated_codec_type"],
			"rig_components": animation_data["rig_components"],
		}
	]

	return result

def write_json_file(file_name, data, selected_json_indent):
	with open(file_name, "w") as json_file:
		json.dump(data, json_file, indent=selected_json_indent)
		print(f"JSON export // Info: Saved file as {file_name}")

def load_skeleton(filename="destiny_player_skeleton.js"):
	try:
		with open(filename, "r") as f:
			return json.load(f)
	except FileNotFoundError:
		print(f"JSON export // Error: Skeleton file '{filename}' not found")
		sys.exit(6)
	except json.JSONDecodeError as e:
		print(f"JSON export // Error: Failed to parse skeleton JSON: {e}")
		sys.exit(7)

def detect_rig(animation_data, game_version):
	runtime_rig_game = game_version_to_rig_runtime_version[game_version]

	player_runtime_rig = (
		d1_player_runtime_rig
		if runtime_rig_game == Player_runtime_rig_version.D1
		else d2_player_runtime_rig
	)

	if compare_rig_components_to_known_rig(cinematic_rig, animation_data["rig_components"]):
		print("Detect rig // Info: Rig detected: player cinematic rig")
		return Rig_types.CINEMATIC, runtime_rig_game

	if compare_rig_components_to_known_rig(player_runtime_rig, animation_data["rig_components"]):
		print("Detect rig // Info: Rig detected: player runtime rig")
		return Rig_types.RUNTIME, runtime_rig_game

	print("Detect rig // Info: Unknown rig! Can only output raw animation data")
	return None, runtime_rig_game

def export_animation(target, animation_data, bone_data, game_version, out_filename, indent):
	# detect rig
	#rig_type, runtime_rig_game = detect_rig(animation_data, game_version)
	rig, compatible_levels = find_compatible_rig(animation_data["rig_components"], game_version)

	# load skeleton if needed
	skeleton = None
	if target != Export_target.JSON_RAW:
		skeleton = load_skeleton()
	print("Animation export // Info: Export target:", target)

	if target == Export_target.JSON_RAW or rig is None:
		result_filename = f"{out_filename}.json"
		# no bones annotations, becasue these are controls
		result = compose_result_animation(animation_data, bone_data)
		write_json_file(result_filename, result, indent)
	else:
		rig_type = rig["type"]

		if rig_type == Rig_types.CINEMATIC:
			if target == Export_target.JSON_RETARGET:
				result_filename = f"{out_filename}.json"
				transform_and_annotate_tracks(bone_data, skeleton)
				result = compose_result_animation(animation_data, bone_data)
				write_json_file(result_filename, result, indent)

			elif target == Export_target.GLTF_RETARGET:
				result_filename = f"{out_filename}.gltf"
				transform_and_annotate_tracks(bone_data, skeleton)
				export_gltf(skeleton, bone_data, "local", result_filename)

		elif rig_type == Rig_types.RUNTIME:
			mode = "local"

			result_tracks = rig_retarget(rig, compatible_levels, animation_data, bone_data, skeleton, mode)

			if target == Export_target.JSON_RETARGET:
				result_filename = f"{out_filename}.json"
				result = compose_result_animation(animation_data, result_tracks)
				write_json_file(result_filename, result, indent)

			elif target == Export_target.GLTF_RETARGET:
				result_filename = f"{out_filename}.gltf"
				export_gltf(skeleton, result_tracks, mode, result_filename)

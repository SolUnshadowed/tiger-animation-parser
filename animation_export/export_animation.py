import logging
import jsonpickle

from dataclasses import asdict

from .enums import Export_Target
from tag.game_version import Game_Version
from runtime_rig.rig_retarget import rig_retarget
from tag_readers.read_skeleton import read_skeleton, Skeleton_Secondary_Class_Mismatch_Exception, Skeleton
from tag_readers.read_rig import read_runtime_rig, Rig_Secondary_Class_Mismatch_Exception, Runtime_Rig_Data
from tag_readers.read_animation import Animation_Data
from animation_decoding.decode_animation import Bone_Tracks
from .gltf_export import export_gltf
from .convert_animation_object_to_local import convert_obj_to_local
from .enums import Animation_Space


logger = logging.getLogger(__name__)


def animation_to_json(animation_data: Animation_Data, bone_tracks: list[Bone_Tracks]):
	result = [
		{
			"bone_tracks": [
				asdict(
					Bone_Tracks(
						track.bone_name_hash,
						track.scales.tolist() if track.scales is not None else [],
						track.rotations.tolist() if track.rotations is not None else [],
						track.translations.tolist() if track.translations is not None else []
					)
				) for track in bone_tracks
			],
			"frame_count": animation_data.animation_header.frame_count,
			"node_count": animation_data.animation_header.node_count,
			"rig_control_count": animation_data.animation_header.rig_control_count,
			"static_codec_type": animation_data.static_bones_header.codec_type if animation_data.static_bones_header is not None else -1,
			"animated_codec_type": animation_data.animated_bones_header.codec_type if animation_data.animated_bones_header is not None else -1,
			"rig_components": [asdict(x) for x in animation_data.runtime_rig_components],
		}
	]

	return result


def write_json_file(file_name, data, selected_json_indent):
	with open(file_name, "w") as json_file:
		json_file.write(jsonpickle.encode(data, indent=selected_json_indent))
		logger.info(f"Saved json file as {file_name}")


def load_skeleton(filename, game_version: Game_Version) -> Skeleton | None:
	try:
		with open(filename, "rb") as tag:
			skeleton_data: Skeleton = read_skeleton(tag, game_version)

		return skeleton_data  # TODO: use original instead of json

	except FileNotFoundError:
		logger.critical(f"Skeleton file '{filename}' not found")
		return None

	except Skeleton_Secondary_Class_Mismatch_Exception as e:
		logger.critical(e)
		return None


def load_rig(filename, game_version: Game_Version) -> Runtime_Rig_Data | None:
	try:
		with open(filename, "rb") as tag:
			rig_data = read_runtime_rig(tag, game_version)

		return rig_data

	except FileNotFoundError:
		logger.critical(f"Runtime rig file '{filename}' not found")
		return None

	except Rig_Secondary_Class_Mismatch_Exception as e:
		logger.critical(e)
		return None


def export_animation(animation_data: Animation_Data, tracks: list[Bone_Tracks], options):
	rig = None
	skeleton = None

	if options.target != Export_Target.JSON_RAW:
		skeleton: Skeleton | None = load_skeleton(options.skeleton, options.version)
		rig: Runtime_Rig_Data | None = load_rig(options.rig, options.version)

	logger.info(f"Preferred export target: {options.target.value}")

	if options.target == Export_Target.JSON_RAW or rig is None or skeleton is None:
		logger.info(f"Used export target: {Export_Target.JSON_RAW.value}")

		result_filename = f"{options.output}.json"
		# no bones annotations, because these are controls
		animation_json = animation_to_json(animation_data, tracks)
		write_json_file(result_filename, animation_json, options.json_indent)

	else:
		logger.info(f"Used export target: {options.target.value}")

		result_tracks: list[Bone_Tracks] = rig_retarget(animation_data, tracks, skeleton, rig)

		if options.animation_space == Animation_Space.LOCAL:
			result_tracks: list[Bone_Tracks] = convert_obj_to_local(animation_data, result_tracks, skeleton)

		if options.target == Export_Target.JSON_RETARGET:
			result_filename = f"{options.output}.json"
			animation_json = animation_to_json(animation_data, result_tracks)
			write_json_file(result_filename, animation_json, options.json_indent)

		elif options.target == Export_Target.GLTF_RETARGET:
			result_filename = f"{options.output}.gltf"
			export_gltf(skeleton, result_tracks, options.animation_space, result_filename, options.name_convention)

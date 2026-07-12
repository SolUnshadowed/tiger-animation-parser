import logging
import sys
import logging

from cli.cli_parser import parse_cli_args
from tag_readers.read_animation import read_animation, Animation_Data
from animation_decoding.decode_animation import decode_animation, Bone_Tracks
from animation_export.export_animation import export_animation
from parser_log_functions import log_animation_header, log_codec_header, log_runtime_rig_components


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)


def read_file(options):
	try:
		with open(options.clip, "rb") as file_desc:
			animation: Animation_Data = read_animation(file_desc, options.version)
			tracks: list[Bone_Tracks] = decode_animation(animation)

		log_animation_header(animation.animation_header)

		if animation.static_bones_header is not None:
			log_codec_header(animation.static_bones_header, "Static")
		else:
			logger.info("No static bones header")

		if animation.animated_bones_header is not None:
			log_codec_header(animation.animated_bones_header, "Animated")
		else:
			logger.info("No animated bones header")

		log_runtime_rig_components(animation.runtime_rig_components)

		if animation is not None:
			export_animation(animation, tracks, options)
		else:
			logger.info("Animation was not parsed")

	except Exception as e:
		logger.critical(e)



if __name__ == "__main__":
	try:
		options = parse_cli_args()

		read_file(options)

		sys.exit(0)
	except FileNotFoundError as e:
		print(e)
		sys.exit(1)
	except PermissionError as e:
		print(e)
		sys.exit(1)

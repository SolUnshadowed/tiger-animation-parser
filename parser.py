import sys

from enums import Game_version, Player_runtime_rig_version, Export_target
from cli_parser import parse_cli_args
from binary_animation_parser import parse_animation_file
from animation_export import export_animation

def read_file(in_filename, game_version, out_filename, json_indent, target):
	with open(in_filename, "rb") as file_desc:
		animation = parse_animation_file(file_desc, game_version)

	if animation is None:
		print("Error // Animation was not parsed")
		sys.exit(5)

	export_animation(
		target,
		animation["animation_data"],
		animation["bone_data"],
		game_version,
		out_filename or in_filename,
		json_indent
	)

if __name__ == "__main__":
	args = sys.argv[1:]

	options = parse_cli_args(args)

	read_file(
		options['selected_file'],
		options['selected_game_version'],
		options['selected_output_file'],
		options['selected_json_indent'],
		options['selected_target']
	)

	sys.exit(0)

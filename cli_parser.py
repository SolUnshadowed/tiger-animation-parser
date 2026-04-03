import sys
import os.path
from enum import Enum

from enums import Game_version, Export_target

class CMD_flags(str, Enum):
	GAME_VERSION =     "-v"
	INPUT_FILE =       "-f"
	OUTPUT_FILE_NAME = "-o"
	JSON_INDENT =      "-i"
	EXPORT_TARGET =    "-t"

def parse_cli_args(args):
	selected_game_version = None
	selected_file = None
	selected_output_file = None
	selected_json_indent = None
	selected_target = Export_target.JSON_RAW

	i = 0
	arg_len = len(args)
	found_key_value_flag = False
	flag_value = ""

	while i < arg_len:
		current = args[i]
		if not found_key_value_flag: # previous is not flag, current arg should be flag
			try:
				flag_value = CMD_flags(current)
				found_key_value_flag = True
			except ValueError:
				allowed = ", ".join(f'"{f.value}"' for f in CMD_flags)
				print(f"argument '{current}' is not an allowed flag")
				print("possible flags:", allowed)
				sys.exit(1)

		else: # previous was a flag, current arg should be value
			if flag_value == CMD_flags.GAME_VERSION:
				try:
					selected_game_version = Game_version(current)
				except ValueError:
					print(f"argument '{current}' is not a supported game version")
					print(
						"possible versions:",
						", ".join(f'"{v.value}"' for v in Game_version)
					)
					sys.exit(1)
			elif flag_value == CMD_flags.INPUT_FILE:
				if os.path.isfile(current):
					selected_file = current
				else:
					print(f"file '{current}' does not exist")
					sys.exit(1)
			elif flag_value == CMD_flags.OUTPUT_FILE_NAME:
				directory = os.path.dirname(current) or "."

				if os.path.exists(directory):
					if os.access(directory, os.W_OK):
						selected_output_file = current
					else:
						print(f"no access to directory '{directory}'")
						sys.exit(1)
				else:
					print(f"directory '{directory}' does not exist")
					sys.exit(1)
			elif flag_value == CMD_flags.JSON_INDENT:
				if current.isnumeric():
					selected_json_indent = int(current)
				else:
					print(f"argument '{current}' is not a number, no indents will be used")
			elif flag_value == CMD_flags.EXPORT_TARGET:
				try:
					selected_target = Export_target(current)
				except ValueError:
					print(f"argument '{current}' is not an supported target")
					print(
						"possible targets:",
						", ".join(f'"{t.value}"' for t in Export_target)
					)
					sys.exit(1)

			found_key_value_flag = False
			flag_value = ""
		i += 1

	if (found_key_value_flag):
		print(f"No value provided for flag '{flag_value}'")
		sys.exit(1)
	if selected_game_version is None:
		print("No file provided, exiting")
		sys.exit(2)
	if selected_file is None:
		print("No game version provided, exiting")
		sys.exit(2)

	return {
		"selected_game_version": selected_game_version,
		"selected_file": selected_file,
		'selected_output_file': selected_output_file,
		'selected_json_indent': selected_json_indent,
		'selected_target': selected_target,
	}

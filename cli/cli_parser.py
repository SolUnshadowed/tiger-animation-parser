import os.path
import argparse

from animation_export.enums import Export_Target, Name_Convention, Animation_Space
from tag.game_version import Game_Version


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument(
	"-v", "--version",
	help="game version",
	type=str,
	choices=[c.value for c in Game_Version],
	required=True
)
parser.add_argument("--clip", help="path to animation clip tag binary file", required=True)
parser.add_argument("--skeleton", help="path to skeleton tag binary file", required=True)
parser.add_argument("--rig", help="path to runtime rig tag binary file", required=True)
parser.add_argument(
	"-t", "--target",
	help="export target",
	choices=[c.value for c in Export_Target],
	default=Export_Target.JSON_RAW.value,
	type=str,
)
parser.add_argument(
	"-i", "--json-indent",
	help="number of spaces to use for JSON indentation",
	type=int,
	default=None,
)
parser.add_argument(
	"--name-convention",
	help="bone name convention",
	choices=[c.value for c in Name_Convention],
	default=Name_Convention.FNV1BE.value,
	type=str,
)
parser.add_argument(
	"--animation-space",
	help="export animation space",
	type=str,
	choices=[c.value for c in Animation_Space],
	default=Animation_Space.LOCAL.value,
)
parser.add_argument("-o", "--output", help="output file path without extension")


def parse_cli_args():
	args = parser.parse_args()

	# if no argument
	if args.output is None:
		args.output = args.clip

	# check args
	if not os.path.isfile(args.clip):
		raise FileNotFoundError(f"missing clip: {args.clip}")

	if not os.path.isfile(args.skeleton):
		raise FileNotFoundError(f"missing skeleton: {args.skeleton}")

	if not os.path.isfile(args.rig):
		raise FileNotFoundError(f"missing runtime rig: {args.rig}")

	out_directory = os.path.dirname(args.output) or "."

	if os.path.exists(out_directory):
		if not os.access(out_directory, os.W_OK):
			raise PermissionError(f"no write access: {out_directory}")
	else:
		FileNotFoundError(f"directory does not exist: {out_directory}")

	# convert strings to enums
	args.version = Game_Version(args.version)
	args.target = Export_Target(args.target)
	args.name_convention = Name_Convention(args.name_convention)
	args.animation_space = Animation_Space(args.animation_space)

	return args


if __name__ == "__main__":
	print(parse_cli_args())

from enum import Enum

from .game_version import Game_Version


class Endianness(str, Enum):
	LE = "<"
	BE = ">"
	def __str__(self):
		return '%s' % self.value


Game_version_to_endianness: dict[Game_Version, Endianness] = {
	Game_Version.D1_DEV_ALPHA: Endianness.BE,
	Game_Version.D1_ROI: Endianness.LE,
	Game_Version.D2_SK: Endianness.LE,
	Game_Version.D2_EOF: Endianness.LE,
	Game_Version.MARATHON: Endianness.LE,
}


def get_game_endianness(game_version: Game_Version) -> Endianness:
	return Game_version_to_endianness[game_version]

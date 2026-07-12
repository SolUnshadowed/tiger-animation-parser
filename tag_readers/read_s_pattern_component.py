from typing import BinaryIO
from dataclasses import dataclass

from tag.endianness import get_game_endianness
from tag.tag_pointers import Rel_Pointer
from tag.type_read_functions import read_u32, read_u64
from tag.game_version import Game_Version


@dataclass
class S_Pattern_Component_Header:
	file_size: int
	default_instance_pointer: Rel_Pointer
	definition_pointer: Rel_Pointer


def read_s_pattern_component_header(f: BinaryIO, game_version: Game_Version) -> S_Pattern_Component_Header:
	f.seek(0)

	endianness = get_game_endianness(game_version)
	file_size = 0

	if game_version == Game_Version.D1_DEV_ALPHA:
		file_size = read_u32(f, endianness)

		f.seek(8 * 4, 1)  # skip to pointers
	else:
		file_size = read_u64(f, endianness)

	rel_pointer_0 = Rel_Pointer(f, game_version)  # no idea
	default_instance_pointer = Rel_Pointer(f, game_version)  # to self reference tag and some number
	definition_pointer = Rel_Pointer(f, game_version)  # to main data

	return S_Pattern_Component_Header(
		file_size=file_size,
		default_instance_pointer=default_instance_pointer,
		definition_pointer=definition_pointer,
	)

from typing import BinaryIO

from .type_read_functions import read_pointer_block
from .game_version import Game_Version


class Base_Tag_Pointer:
	def __init__(self, game_version: Game_Version):
		self.game_version: Game_Version = game_version
		self.offset_address: int = 0
		self.offset: int = 0

	def get_address(self) -> int:
		return self.offset_address + self.offset

	def __str__(self) -> str:
		return f"game: {self.game_version}, address: {hex(self.offset_address)}, offset: {self.offset}"

	def is_zero(self) -> bool:
		return self.offset == 0


class Dummy_Pointer(Base_Tag_Pointer):
	def __init__(self, offset, game_version: Game_Version):
		super().__init__(game_version)

		self.offset: int = offset


class Rel_Pointer(Base_Tag_Pointer):
	def __init__(self, f: BinaryIO, game_version: Game_Version):
		super().__init__(game_version)

		self.offset_address: int = f.tell()
		self.offset: int = read_pointer_block(f, game_version)


class Vec_Pointer(Base_Tag_Pointer):
	def __init__(self, f: BinaryIO, game_version: Game_Version):
		super().__init__(game_version)

		self.length_address: int = f.tell()
		self.length: int = read_pointer_block(f, game_version)

		self.offset_address: int = f.tell()
		self.offset: int = read_pointer_block(f, game_version)

	def __str__(self) -> str:
		return f"game: {self.game_version},  address: {hex(self.length_address)},  length: {self.length},  offset: {self.offset}"

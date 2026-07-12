import logging
import numpy as np
import numpy.typing as npt

from typing import BinaryIO, Iterator, Callable, Any

from .endianness import get_game_endianness, Endianness
from .tag_pointers import Base_Tag_Pointer
from .game_version import Game_Version
from .type_read_functions import read_pointer_block


logger = logging.getLogger(__name__)


class Tag_Array[T]:
	def __init__(
		self,
		f: BinaryIO,
		pointer: Base_Tag_Pointer,
		read_func: Callable[[BinaryIO, Endianness], T]
	):
		self.game_version: Game_Version = pointer.game_version

		endianness: Endianness = get_game_endianness(self.game_version)
		address = pointer.get_address()

		f.seek(address)

		self.length = read_pointer_block(f, self.game_version)
		self.array_type = read_pointer_block(f, self.game_version)

		if self.game_version == Game_Version.D1_DEV_ALPHA:
			f.seek(8, 1)  # dev_alpha has padding

		self.payload: list[T] = []

		if self.length > 0:
			self.payload_start = f.tell()
			self.payload = [ read_func(f, endianness) for _ in range(self.length) ]

		else:
			logger.info(f"Empty array at: {hex(address)}")

	def __str__(self):
		return f"game: {self.game_version}, length: {self.length}, type: {hex(self.array_type)}"

	def read_vec(self, offset: int, amount: int) -> tuple[list[T], int]:
		new_offset = offset + amount
		return self.payload[offset: new_offset], new_offset

	def read_single(self, offset) -> T:
		return self.payload[offset]

	def __getitem__(self, index: int) -> T:
		return self.payload[index]

	def __iter__(self) -> Iterator[T]:
		return iter(self.payload)

	def __len__(self) -> int:
		return self.length


class Tag_Array_NP:
	data: npt.NDArray[Any]

	def __init__(
			self,
			f: BinaryIO,
			pointer: Base_Tag_Pointer,
			dtype: npt.DTypeLike,
			inner_size: int = 1
	):
		self.game_version = pointer.game_version
		endianness: Endianness = get_game_endianness(self.game_version)

		f.seek(pointer.get_address())
		self.length = read_pointer_block(f, self.game_version)
		self.array_type = read_pointer_block(f, self.game_version)

		if self.game_version == Game_Version.D1_DEV_ALPHA:
			f.seek(8, 1)

		if self.length > 0:
			base_dtype = np.dtype(dtype).newbyteorder(endianness)

			total_scalars = self.length * inner_size
			raw_data = np.fromfile(f, dtype=base_dtype, count=total_scalars)

			if inner_size > 1:
				self.data = raw_data.reshape((self.length, inner_size))
			else:
				self.data = raw_data
		else:
			self.data = np.array([], dtype=dtype)
			if inner_size > 1:
				self.data = self.data.reshape((0, inner_size))

	def read_vec(self, offset: int, amount: int) -> tuple[np.ndarray, int]:
		new_offset = offset + amount
		return self.data[offset: new_offset], new_offset

	def read_scalar(self, offset: int) -> tuple[Any, int]:
		return self.data[offset], offset + 1

	def __len__(self) -> int:
		return self.length

	def __getitem__(self, index: int) -> Any:
		return self.data[index]

	def __iter__(self) -> Iterator[Any]:
		return iter(self.data)

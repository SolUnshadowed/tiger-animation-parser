from type_read_functions import *

class Rel_pointer:
	def __init__(self, f):
		self.offset_address = f.tell()
		self.offset = read_u64(f)

	def get_address(self):
		return self.offset_address + self.offset

	def __str__(self):
		return f"address: {self.offset_address}, offset: {self.offset}"

class Vec_pointer:
	def __init__(self, f):
		self.length_address = f.tell()
		self.length = read_u64(f)

		self.offset_address = f.tell()
		self.offset = read_u64(f)

	def get_address(self):
		return self.offset_address + self.offset

	def __str__(self):
		return f"address: {self.length_address}, length: {self.length}, offset: {self.offset}"

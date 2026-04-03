from type_read_functions import *

class Tag_array:
	def __init__(self, f, pointer, read_func=None):

		address = pointer.get_address()
		f.seek(address)

		self.length = read_u64(f)
		self.type = read_u64(f)
		self.payload_length = 0
		self.payload = []

		if (self.length > 0):
			self.payload_start = f.tell()

			if read_func is not None:
				self.payload = [ read_func(f) for _ in range(self.length) ]
			else:
				print(f"Tag_array // Error: Read function is not provided")
		else:
			print("Tag_array // Info: empty array")

		if len(self.payload) > 0:
			self.payload_length = len(self.payload)

	def __str__(self):
		return f"length: {self.length}, type: {hex(self.type)}"

	def read_vec(self, offset, n):
		new_offset = offset + n
		return self.payload[offset: new_offset], new_offset

	def read(self, offset):
		return self.payload[offset]

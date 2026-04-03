import struct

def read_u32(f):
	return struct.unpack("<I", f.read(4))[0]

def read_u32_array(f, length):
	return struct.unpack(f"< {length}I", f.read(4 * length))

def read_s32(f):
	return struct.unpack("<i", f.read(4))[0]

def read_u64(f):
	return struct.unpack("<Q", f.read(8))[0]

def read_u16(f):
	return struct.unpack("<H", f.read(2))[0]

def read_u16_array(f, length):
	return struct.unpack(f"< {length}H", f.read(2 * length))

def read_s16(f):
	return struct.unpack("<h", f.read(2))[0]

def read_u8(f):
	return struct.unpack("<B", f.read(1))[0]

def read_u8_array(f, length):
	return struct.unpack(f"< {length}B", f.read(length))

def read_s8(f):
	return struct.unpack("<b", f.read(1))[0]

def read_s8_array(f, length):
	return struct.unpack(f"< {length}b", f.read(length))

def read_f32(f):
	return struct.unpack("<f", f.read(4))[0]

def read_f32_array(f, length):
	return struct.unpack(f"< {length}f", f.read(4 * length))

def read_vec4_array(f, length):
	result = []

	for i in range(length):
		vec4 = read_f32_array(f, 4)
		result.append(vec4)

	return result

def read_vec4(f):
	return read_f32_array(f, 4)

def u32_to_le_hex(value: int) -> str:
    return value.to_bytes(4, byteorder='little', signed=False).hex().upper()

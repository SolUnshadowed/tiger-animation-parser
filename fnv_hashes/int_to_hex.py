def u32_to_le_hex(value: int) -> str:
	return value.to_bytes(4, byteorder='little', signed=False).hex().upper()


def u32_to_be_hex(value: int) -> str:
	return value.to_bytes(4, byteorder='big', signed=False).hex().upper()
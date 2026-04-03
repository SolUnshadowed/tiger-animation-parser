def calculate_tangent(byte_val, point_0, point_1, upper=True):
	"""
	Same as in TagTool / CurveCodec / CalculateTangent
	upper=True -> upper 4 bits, lower otherwise
	"""
	val = (byte_val >> 4) if upper else (byte_val & 15)
	tan = (val - 7)

	return (abs(tan) / 7) * (tan / 7 * 0.3) + (point_1 - point_0)

def hermite(point_0, point_1, tan_0, tan_1, time):
	"""Cubic Hermite as in TagTool / CurveCodec / CalculateCurvePosition"""
	h_00 = 2 * time**3 - 3 * time**2 + 1
	h_10 = time**3 - 2 * time**2 + time
	h_01 = 3 * time**2 - 2 * time**3
	h_11 = time**3 - time**2
	return h_00 * point_0 + h_10 * tan_0 + h_01 * point_1 + h_11 * tan_1

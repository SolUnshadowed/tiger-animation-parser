import numpy as np

def calculate_tangent(byte_val, point_0, point_1, upper=True):
	"""
	Same as in TagTool / CurveCodec / CalculateTangent
	upper=True -> upper 4 bits, lower otherwise
	"""
	as_int = np.int32(byte_val)
	val = (as_int >> 4) if upper else (as_int & 15)
	tan = val - 7

	return (abs(tan) / 7) * (tan / 7 * 0.3) + (point_1 - point_0)


def hermite(point_0, point_1, tan_0, tan_1, time):
	"""Cubic Hermite as in TagTool / CurveCodec / CalculateCurvePosition"""
	time_sq = time**2
	time_cb = time**3
	h_00 = 2 * time_cb - 3 * time_sq + 1
	h_10 = time_cb - 2 * time_sq + time
	h_01 = 3 * time_sq - 2 * time_cb
	h_11 = time_cb - time_sq
	return h_00 * point_0 + h_10 * tan_0 + h_01 * point_1 + h_11 * tan_1

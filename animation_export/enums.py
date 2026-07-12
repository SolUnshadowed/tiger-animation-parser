from enum import Enum


class Export_Target(str, Enum):
	JSON_RAW = "json_raw"
	JSON_RETARGET = "json_retarget"
	GLTF_RETARGET = "gltf_retarget"


class Name_Convention(str, Enum):
	BUNGIE = "bungie"
	FNV1LE = "fnv1le"
	FNV1LE_NO_ZEROES = "fnv1le_no_zeroes"
	FNV1BE = "fnv1be"
	FNV1BE_NO_ZEROES = "fnv1be_no_zeroes"
	BLENDER = "blender"


class Animation_Space(str, Enum):
	OBJECT = "object"
	LOCAL = "local"

from enum import Enum

class Game_version(str, Enum):
	D1_ROI = "d1_roi"
	D2_SK = "d2_sk"
	D2_EOF = "d2_eof"
	MARATHON = "marathon"

class Player_runtime_rig_version(Enum):
	D1 = 0
	D2 = 1

class Rig_types(Enum):
	CINEMATIC = 0
	RUNTIME = 1

class Export_target(str, Enum):
	JSON_RAW = "json_raw"
	JSON_RETARGET = "json_retarget"
	GLTF_RETARGET = "gltf_retarget"

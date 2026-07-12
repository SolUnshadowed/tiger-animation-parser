from enum import Enum


class Game_Version(str, Enum):
	D1_DEV_ALPHA = "d1_devalpha"
	D1_ROI = "d1_roi"
	D2_SK = "d2_sk"
	D2_EOF = "d2_eof"
	MARATHON = "marathon"
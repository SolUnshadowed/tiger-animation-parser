from dataclasses import dataclass


@dataclass(slots=True)
class Rig_Component:
	hash: int
	count: int


@dataclass(slots=True)
class Control_Relation:
	payload_0: tuple[int, int, int, int, int, int]
	coof_0: float
	payload_1: tuple[int, int, int, int, int, int, int]
	coof_1: float
	payload_2: tuple[int, int, int, int, int, int, int]


@dataclass(slots=True)
class Control_Relation_D2(Control_Relation):
	hash: int


@dataclass(slots=True)
class Skeleton_Node_Def:
	bone_hash: int
	parent_node_index: int
	first_child_node_index: int
	next_sibling_node_index: int


@dataclass(slots=True)
class Transform:
	r:  tuple[float, float, float, float]
	ts: tuple[float, float, float, float]

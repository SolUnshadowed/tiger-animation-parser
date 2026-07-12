from dataclasses import dataclass
from enum import IntEnum

from tag.data_structures import Control_Relation
from tag_readers.read_rig import Runtime_Rig_Data


class Constraint_Type(IntEnum):
	PARENT = 0
	POINT_AND_ORIENT = 1


class IK_Function_Type(IntEnum):
	NONE = -1
	IK_3 = 0
	RFK = 1


class Space_Type(IntEnum):
	RELATIVE = 0
	PARENT = 1
	OBJECT = 2
	UNK_3 = 3
	BIND = 4
	AVERAGE = 5
	AIM = 6


@dataclass(slots=True)
class Space_Def:
	bone_index_0: int
	bone_index_1: int
	space_type: Space_Type


@dataclass(slots=True)
class Constraint:
	rot_space_0: Space_Def
	rot_space_1: Space_Def
	aim_influence: float
	prob_flags_0: int
	tr_space_0: Space_Def
	tr_space_1: Space_Def
	coof_1: float
	prob_flags_1: int
	bone_index: int
	ik_chain_start_bone_index: int
	constraint_type: Constraint_Type
	ik_function_type: IK_Function_Type
	unk_0: int
	unk_1: int


def control_relation_to_constraint(relation: Control_Relation) -> Constraint:
	rot_space_0 = Space_Def(relation.payload_0[0], relation.payload_0[1], Space_Type(relation.payload_0[2]))
	rot_space_1 = Space_Def(relation.payload_0[3], relation.payload_0[4], Space_Type(relation.payload_0[5]))
	coof_0 = relation.coof_0
	prob_flags_0 = relation.payload_1[0]
	tr_space_0 = Space_Def(relation.payload_1[1], relation.payload_1[2], Space_Type(relation.payload_1[3]))
	tr_space_1 = Space_Def(relation.payload_1[4], relation.payload_1[5], Space_Type(relation.payload_1[6]))
	coof_1 = relation.coof_1
	prob_flags_1 = relation.payload_2[0]
	bone_index = relation.payload_2[1]
	ik_chain_start_bone_index=relation.payload_2[2]
	constraint_type = Constraint_Type(relation.payload_2[3])
	ik_function_type = IK_Function_Type(relation.payload_2[4])
	unk_0 = relation.payload_2[5]
	unk_1 = relation.payload_2[6]

	return Constraint(
		rot_space_0=rot_space_0,
		rot_space_1=rot_space_1,
		aim_influence=coof_0,
		prob_flags_0=prob_flags_0,
		tr_space_0=tr_space_0,
		tr_space_1=tr_space_1,
		coof_1=coof_1,
		prob_flags_1=prob_flags_1,
		bone_index=bone_index,
		ik_chain_start_bone_index=ik_chain_start_bone_index,
		constraint_type=constraint_type,
		ik_function_type=ik_function_type,
		unk_0=unk_0,
		unk_1=unk_1,
	)


def fill_constraints(runtime_rig_data: Runtime_Rig_Data) -> list[Constraint]:
	return [control_relation_to_constraint(x) for x in runtime_rig_data.controls_relations]

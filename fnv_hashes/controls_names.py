from int_to_hex import u32_to_be_hex

rig_control_hash_to_name = {
	46292159: "left_upperarm",
	260387574: "pelvis",
	323230667: "right_lower_lip_corner",
	526126167: "sternum",
	643770316: "right_ring_finger_3",
	643770317: "right_ring_finger_2",
	643770318: "right_ring_finger_1",
	685144220: "right_forearm",
	780552125: "jaw",
	911251146: "right_brow_1",
	1109843168: "right_foot",
	1162244392: "right_index_finger_1",
	1162244394: "right_index_finger_3",
	1162244395: "right_index_finger_2",
	1574152469: "left_shoulder_twist",
	1870004816: "left_eye_1",
	1903516093: "right_middle_finger_1",
	1903516094: "right_middle_finger_2",
	1903516095: "right_middle_finger_3",
	1991716991: "left_upper_lip_corner",
	2082073985: "left_grip",
	2197551961: "right_clavicle",
	2247417708: "right_pinky_finger_2",
	2247417709: "right_pinky_finger_3",
	2247417711: "right_pinky_finger_1",
	2269793694: "right_upperarm",
	2294000752: "right_grip",
	2378126911: "utility",
	2384589008: "right_toe",
	2462053155: "right_eye_1",
	2514648495: "right_hand",
	2544092651: "pedestal",
	2613742458: "left_lower_lip_corner",
	2852814614: "left_hand",
	2876951832: "left_thumb_2",
	2876951833: "left_thumb_3",
	2876951835: "left_thumb_1",
	2912056140: "left_middle_finger_3",
	2912056141: "left_middle_finger_2",
	2912056142: "left_middle_finger_1",
	2927220804: "left_upper_eyelid",
	3218606139: "left_brow_1",
	3225703531: "left_forearm",
	3448274439: "head",
	3458995415: "left_thigh",
	3592572753: "left_ring_finger_1",
	3592572754: "left_ring_finger_2",
	3592572755: "left_ring_finger_3",
	3716183592: "right_thumb_1",
	3716183594: "right_thumb_3",
	3716183595: "right_thumb_2",
	3745546460: "right_shoulder_twist",
	3757203715: "left_toe",
	3768937134: "spine_base",
	3939896241: "left_foot",
	3979568405: "left_index_finger_1",
	3979568406: "left_index_finger_2",
	3979568407: "left_index_finger_3",
	4082597298: "right_upper_lip_corner",
	4085946028: "left_pinky_finger_3",
	4085946029: "left_pinky_finger_2",
	4085946030: "left_pinky_finger_1",
	4128298536: "neck_base",
	4146284764: "right_thigh",
	4206468413: "right_upper_eyelid",
	4287601556: "left_clavicle",
	3628876502: "neck_3",
	3628876497: "neck_4",
	2301832844: "tail_2",
	2301832845: "tail_3",
	2301832842: "tail_4",
	1837674707: 'spine_4',
	1880963441: 'tail_base'
}

unofficial_names = {
	1114585702: "*control for b_l_wrist_twist_fixup",
	1399022973: "*control for b_r_wrist_twist_fixup"
}


def resolve_control_name(control_hash):
	if control_hash in rig_control_hash_to_name:
		return rig_control_hash_to_name[control_hash]
	elif control_hash in unofficial_names:
		return unofficial_names[control_hash]
	else:
		return u32_to_be_hex(control_hash)

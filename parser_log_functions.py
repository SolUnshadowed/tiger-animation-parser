import logging

from tag.tag_array import Tag_Array
from tag.data_structures import Rig_Component
from fnv_hashes.int_to_hex import u32_to_be_hex
from fnv_hashes.rig_components import components


logger = logging.getLogger(__name__)


def log_animation_header(animation_header):
	logger.info("Animation header:")
	logger.info(f"\tframes: {animation_header.frame_count}")
	logger.info(f"\tstatic scaled bones: {animation_header.static_scale_control_map_pointer.length}")
	logger.info(f"\tstatic rotated bones: {animation_header.static_rotation_control_map_pointer.length}")
	logger.info(f"\tstatic translated bones: {animation_header.static_translation_control_map_pointer.length}")
	logger.info(f"\tanimated scaled bones: {animation_header.animated_scale_control_map_pointer.length}")
	logger.info(f"\tanimated rotated bones: {animation_header.animated_rotation_control_map_pointer.length}")
	logger.info(f"\tanimated translated bones: {animation_header.animated_translation_control_map_pointer.length}")
	logger.info(f"\tanimation hash: {u32_to_be_hex(animation_header.animation_hash)}")
	logger.info(f"\tnode count: {animation_header.node_count}")
	logger.info(f"\trig control count: {animation_header.rig_control_count}")
	logger.info(f"\tframe events: {animation_header.frame_events_array_pointer.length}")
	logger.info(f"\textra data 0: {not animation_header.extra_data_0_pointer.is_zero()}")
	logger.info(f"\textra data 1: {not animation_header.extra_data_1_pointer.is_zero()}")
	logger.info(f"\textra data 2: {not animation_header.extra_data_2_pointer.is_zero()}")
	logger.info(f"\textra data 3: {not animation_header.extra_data_3_pointer.is_zero()}")
	logger.info(f"\textra data 4: {not animation_header.extra_data_4_pointer.is_zero()}")
	logger.info(f"\textra data 5: {not animation_header.extra_data_5_pointer.is_zero()}")
	logger.info(f"\textra data 6: {not animation_header.extra_data_6_pointer.is_zero()}")
	logger.info(f"\textra data 7: {not animation_header.extra_data_7_pointer.is_zero()}")


def log_runtime_rig_components(tag_array: Tag_Array[Rig_Component]):
	logger.info("Runtime rig components:")

	for comp in tag_array.payload:
		fnv_hash = u32_to_be_hex(comp.hash)
		logger.info(f"\thash: {fnv_hash}, count: {comp.count}")
		if fnv_hash in components:
			component = components[fnv_hash]
			logger.info(f"\t\tstring: {component['string']}")
			logger.info(f"\t\tcomment: {component['comment']}")
			logger.info(f"\t\tparent: {component['parent']}")


def log_codec_header(codec_header, type: str):
	logger.info(f"{type} header:")
	logger.info(f"\tcodec type: {codec_header.codec_type}")
	logger.info(f"\tscale_stream_count: {codec_header.scale_stream_count}")
	logger.info(f"\trotation_stream_count: {codec_header.rotation_stream_count}")
	logger.info(f"\ttranslation_stream_count: {codec_header.translation_stream_count}")


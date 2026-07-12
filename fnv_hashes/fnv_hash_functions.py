FNV_32_PRIME = 0x01000193      # 16777619
FNV_32_OFFSET_BASIS = 0x811c9dc5


def fnv1_32(data: bytes) -> int:
    hash_ = FNV_32_OFFSET_BASIS
    for byte in data:
        hash_ = (hash_ * FNV_32_PRIME) & 0xffffffff
        hash_ = hash_ ^ byte
    return hash_


def fnv1a_32(data: bytes) -> int:
    hash_ = FNV_32_OFFSET_BASIS
    for byte in data:
        hash_ = hash_ ^ byte
        hash_ = (hash_ * FNV_32_PRIME) & 0xffffffff
    return hash_

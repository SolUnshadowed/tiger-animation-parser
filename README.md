# tiger-animation-parser

A utility for parsing `s_animation_clip` tags binaries of Tiger engine (Destiny/Destiny 2).

Supports animated codecs 0, 1, 2, 3 and static codec 3.

## Requirements

- Python 3.13+
- Install dependencies:

```bash
pip install -r requirements.txt
````

## Running

```bash
python3 parser.py \
    -v <game_version> \
    --clip <clip_tag_binary> \
    --skeleton <skeleton_tag_binary> \
    --rig <runtime_rig_tag_binary> \
    [-t <export_target>] \
    [--name-convention <name_convention>] \
    [--animation-space <space>] \
    [-i <json_indent>] \
    [-o <output_file_name>]
```

### Arguments

- `-v`, `--version <game_version>` – game version the tags were extracted from. Supported values:
  - `d1_devalpha` - Destiny Internal Alpha
  - `d1_roi` – Destiny latest version (Rise of Iron)
  - `d2_eof` – Destiny 2 (Edge of Fate)
  - `marathon` – Marathon

- `--clip <clip_tag_binary>` – path to the animation clip tag binary.

- `--skeleton <skeleton_tag_binary>` – path to the skeleton tag binary.

- `--rig <runtime_rig_tag_binary>` – path to the runtime rig tag binary.

- `-t`, `--target <export_target>` – export format. Supported targets:
  - `json_raw` – extracts data from the tag and writes it to a JSON file. Uses Z-up, X-forward coordinate order for translations and quaternions. **Default option** and also serves as a fallback if `_retarget` options cannot be used.
  - `json_retarget` – extracts animation data and retargets it according to provided skeleton and runtime rig constraints. Uses a Y-up, Z-forward coordinate system. Output is a JSON file.
  - `gltf_retarget` – same as `json_retarget`, but exports a GLTF file containing the armature and animation. Uses a Y-up, Z-forward coordinate system.

- `--name-convention <name_convention>` – naming convention for exported bones:
  - `fnv1le` – FNV-1 32-bit little-endian hash.
  - `fnv1le_no_zeroes` – FNV-1 32-bit little-endian hash with leading zeroes stripped.
  - `fnv1be` – FNV-1 32-bit big-endian hash. **Default**.
  - `fnv1be_no_zeroes` – FNV-1 32-bit big-endian hash with leading zeroes stripped.
  - `bungie` – attempts reverse hash lookup using known Bungie bone names, falling back to `fnv1be` if no match is found.
  - `blender` – uses Blender exporter addon names for skeletons when possible, falling back to `fnv1be` for unknown bones.

- `--animation-space <space>` - animation space:
  - `local` – bones' transforms are in parent local space. If `gltf_retarget` is selected, hierarchical skeleton will be created. **Default**.
  - `object` - bones' transforms are in character's object space. If `gltf_retarget` is selected, skeleton bones will be children of the same root.

- `-i`, `--json-indent <json_indent>` – number of spaces to use for JSON indentation. If omitted, the JSON will be output in a single line without indentation.

- `-o`, `--output <output_file_name>` – output file path **without an extension**. The extension is determined automatically based on the export target.

# Changelog

## v2.0
- No longer requires skeleton JSON file.
- Removed mathutils dependency
- Added pyglm dependency

# tiger-animation-parser

A utility for parsing `s_animation_clip` tags binaries of Tiger engine (Destiny/Destiny 2).

Supports animated codecs 0, 1, 2, 3 and static codec 3.

## Running

```
python3 parser.py -v <game_version> -f <tag_binary> [-o <output_file_name>] [-i <json_indents>] [-t <export_target>]
```

Flags:
- `<game_version>` – is the version of the game from which the tag was extracted. Suppoted values:
  - `d1_roi` – Destiny latest version (Rise of Iron)
  - `d2_sk` – Destiny 2 last version before Beyond Light (Shadowkeep)
  - `d2_eof` – Destiny 2 (Edge of Fate)
  - `marathon` – Marathon

- `<tag_binary>` – path to the extracted tag binary file.

- `<output_file_name>` – name of the file to be saved **without extension**. The extension is determined automatically based on the export target.

- `<json_indents>` – number of spaces to use for JSON indentation. If omitted or not a number, the JSON will be output in a single line without indentation.

- `<export_target>` – the export format. Supported targets:
  - `json_raw` – extracts data from the tag and writes it to a JSON file. Uses Z-up coordinate order for translations and quaternions. This is the default option and also serves as a fallback if `_retarget` options cannot be used.
  - `json_retarget` – extracts data from the tag and retargets it using player runtime rig constraints if animation is made for player runtime rig. The coordinate system is switched to Z-forward.
    - If a cinematic rig is detected, the animation can be applied to the standard hierarchical player skeleton.
    - If a runtime rig is detected, all bone tracks are retargeted using constraints to fit the standard skeleton.

    Output is a JSON file.
  - `gltf_retarget` – similar to `json_retarget`, but creates a GLTF file with an armature and animation.

## Required Files

This program requires a player skeleton file to work correctly.

- Required file: destiny_player_skeleton.js

- Download link: https://www.bungie.net/common/destiny_content/animations/destiny_player_skeleton.js

- Where to place it: in the same directory as `parser.py`

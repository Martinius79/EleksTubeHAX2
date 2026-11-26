# Notice and attribution

EleksTubeHAX2 is a rewrite of the custom firmware **EleksTubeHAX** (v1) on plain ESP-IDF.
It contains no v1 source code, but builds directly on the hardware knowledge, reverse engineering
and design work collected in v1. This project would not exist without the people below.

Copyright (C) 2026 Clemens Sutor (Martinius79) and the EleksTubeHAX2 contributors.

## Licence

EleksTubeHAX2 is free software, licensed under the **GNU General Public License v3.0 or later**
(SPDX: `GPL-3.0-or-later`), the same licence family as v1. See [LICENSE](LICENSE).
Source files carry an `SPDX-License-Identifier` header.

## Origin projects

- **EleksTubeHAX** by Mark Smith (**@SmittyHalibut**) – the original hack of the EleksTube IPS
  clock and the first open firmware.
- **EleksTubeHAX** continued by Aljaž Ogrin (**@aly-fly**) – https://github.com/aly-fly/EleksTubeHAX –
  support for many clone clocks, maintenance and releases.
- Clemens Sutor (**@Martinius79**) – v1 co-maintainer, board support for most clones, author of v2.

## v1 contributors

Code, fixes, board support or hardware findings in v1 (from the v1 git history and README):

- @icebreaker-ch, @meddle99, @OggyP, @bitrot-alpha – code snippets and features
- @victorvuelma, @gamba69 (Igor K. Dulevich) – Home Assistant support
- @Hans99 – MarvelTubes Mini integration
- @Fastdruid – PunkCyber flashing workaround
- Xander X, Frank Cohen, @Frank-Bemelman, Logan Kennelly, @darkgrue, @MrEcosse (Beyond the Veg),
  @cschwinne, @ExplodingLemur, Pauldy, Spardz, matthewclaude

If you contributed to v1 and are missing here, please open an issue or pull request.

## Third-party components

ESP-IDF and components from the Espressif Component Registry are used under their own licences
(mostly Apache-2.0). Third-party components added later are listed here with name, licence and
source.

| Component | Licence | Source |
|-----------|---------|--------|
| ESP-IDF | Apache-2.0 | https://github.com/espressif/esp-idf |

## Clock-face graphics

v1 clock faces are not included: their origin is undocumented (D-018). Built-in faces are
rendered by `tools/facegen` from geometry only and are original works of this project; their
licence is decided in D-019.

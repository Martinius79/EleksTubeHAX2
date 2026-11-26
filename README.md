# EleksTubeHAX2

A "reloaded" version of the custom firmware for fully digital nixie tube clones – a rewrite of
[EleksTubeHAX](https://github.com/aly-fly/EleksTubeHAX) on plain ESP-IDF.

**Status:** early development, not usable yet. See the [roadmap](docs/ROADMAP.md) and the
[decision log](docs/DECISIONS.md).

## Building

Requires ESP-IDF (v6.1 or newer) in an activated shell:

```sh
python tools/build.py --list          # available image variants (chip x flash size)
python tools/build.py esp32-4MB       # build one variant into build/esp32-4MB
python tools/build.py --all           # build every variant
```

## Credits

Based on the work of Mark Smith (@SmittyHalibut), Aljaž Ogrin (@aly-fly) and all EleksTubeHAX
contributors – see [NOTICE.md](NOTICE.md).

## Licence

GPL-3.0-or-later – see [LICENSE](LICENSE).

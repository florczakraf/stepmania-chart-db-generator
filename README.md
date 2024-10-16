# StepMania Chart DB Generator

## About
This project allows generating a simple filesystem-based database
of StepMania charts. The database is indexed by the chart hash v3 (as
defined by [Simply Love](https://github.com/Simply-Love/Simply-Love-SM5)
theme).

## DB Layout
General layout:
```
<db>/
  metadata.json
  charts/
    00/
      3afbec6280c8b0.json
      ...
    ...
  packs/
    pack name.json
    other pack.json
    ...
```

### `metadata.json`
```
{
  "last_update": "2024-10-16T11:58:12.602603+00:00",
  "num_charts": 3166,
  "num_packs": 10
}
```
`last_update` is expressed in ISO 8601 format.

### `charts`
The `<db>/charts` directory consists of two-level tree:
```
db/
  00/
    008e3f43b2eb91.json
    00c321a2227e2b.json
    ...
  01/
    028a44f02fc616.json
    ...
  ...
  ff/
    ...
    fd5865bffd6fa5.json
```
that together form a full hash of the chart. Json fields are self-explanatory.
Here's an example of a produced json file:
```json
{
  "artist": "CanBlaster",
  "artisttranslit": "",
  "diff": "Easy",
  "diff_number": 7,
  "diffs": [
    "023afbec6280c8b0",
    "043f62c22e303df9",
    "08b5de7c9b62c2de",
    "277087f060b667cd",
    "61ef33cf4fd06dbd",
    "62962dafbf57c92f",
    "dd66127e808ae70d",
    "ed158967ce6bff8f",
    "fa23868b76969788"
  ],
  "hash": "62962dafbf57c92f",
  "pack_name": "ITG Series",
  "packs": [
    "ITG Series",
    "In The Groove 3",
    "itg3"
  ],
  "steps_type": "dance-single",
  "subtitle": "Hardkore",
  "subtitletranslit": "",
  "title": "Disconnected",
  "titletranslit": ""
}
```
`artisttranslit`, `subtitle`, `subtitletranslit`,
`titletranslit` can be empty strings.

`diffs` are a list of other diffs seen next to this particular chart in a single
simfile. It's possible that a single chart exists in multiple packs, thus there
can be many different versions of their "siblings".

Generator assumes that the first occurrence of the chart is the "canonical" one
to not change the artist, title, etc. for every pack that contains it later in
the parsing process. This allows to perform manual tweaks to the database, for
example removing block difficulty from the title that's been added for a
tournament pack.

### `packs`
Each pack has a file in `<db>/packs` directory that contains a list of chart
hashes within that packs, for example:
```
$ cat "db_v2/packs/Yhono Originals.json" 
["b395e84a3a864b96", "a188216a0bc0b837", "4526ddf1c2e112e6", "dd6c5f9c0c6496ef", "96abb92df1877371"]
```

## Usage
```
$ poetry install
$ poetry run sm-db-gen --help
$ poetry run sm-db-gen --workers 12 --db /output/db_v2 /path/to/Songs/ /path/to/other/Songs
```

The above command will look for all `.sm` and `.ssc` files in the provided
directory trees and process them in 12 parallel threads. You might want to
tweak number of workers depending on the type of disk and number of CPU cores
you have. On my machine it processed over 125k simfiles in 5 minutes where
charts were on an HDD and db was being saved to an SSD, 4c/4t i5-4460 CPU.

## License
The project is licensed under GNU Affero General Public License v3.0 or later.

## Thanks
Huge thanks to [Ash Garcia](https://github.com/garcia) for creating
[simfile](https://github.com/garcia/simfile) library that made this project
possible with fewer headaches (but the content created over the decades
is wild -- see the parsing workarounds ;).

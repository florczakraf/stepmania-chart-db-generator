# Stepmania Chart DB Generator

## About
This project allows generating a simple filesystem-based database
of Stepmania charts. The database is indexed by the chart hash (as
defined by [Simply Love](https://github.com/Simply-Love/Simply-Love-SM5)
theme). The output `db` directory consists of two-level tree:
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
  "bpms": "0.000=139.000,36.000=140.000,40.000=150.000,44.000=160.000,48.000=170.000,52.000=180.000,56.000=190.000,60.000=200.000,64.000=210.000,280.000=215.000,284.000=220.000,288.000=225.000,292.000=230.000,296.000=235.000,300.000=240.000,304.000=245.000",
  "diff": "Easy",
  "diff_number": 7,
  "directory": "Disconnected hardkore",
  "hash": "62962dafbf57c92f",
  "pack_name": "In The Groove 3",
  "steps_type": "dance-single",
  "subtitle": "Hardkore",
  "subtitletranslit": "",
  "title": "Disconnected",
  "titletranslit": ""
}
```
`artisttranslit`, `subtitle`, `subtitletranslit`,
`titletranslit` can be empty strings.

## Usage
Make sure you have a `lua` interpreter, `find` and `xargs` available.
```
$ find /path/to/Songs/ \( -name '*.sm' -o -name '*.ssc' \) -print0 | xargs -0 -P 16 -I {} lua parser.lua "{}"
```
The above command will look for all `.sm` and `.ssc`
files in the provided directory tree and pass them to
the `parser.lua` entrypoint one at the time,
up to 16 simultaneous processes. You might want to tweak these
parameters depending on the type of disk and number of CPU cores
you have. On my machine it processed over 7k charts in 30 seconds
using that combo of parameters (charts were on an HDD, db
was being saved to an SSD, 6c/12t i7 CPU).

## Licenses
Code from Simply Love theme and Stepmania as well as other lua libraries
was used here so this project is licensed under the terms of GPL3.
Consult provided license files and in-line comments for details.

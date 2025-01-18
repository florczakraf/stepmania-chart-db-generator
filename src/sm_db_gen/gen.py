import argparse
import concurrent.futures
import os
from collections import Counter
from functools import partial
from hashlib import sha1
from io import StringIO
from pathlib import Path
from pprint import pprint

import simfile
import tqdm

from sm_db_gen.db import STORAGE_DRIVERS, Chart, InMemStorage, StorageV2
from sm_db_gen.reference import get_v1_reference

DIFF_MAPPING = {
    # based on SM
    "beginner": "Beginner",
    "easy": "Easy",
    "basic": "Easy",
    "light": "Easy",
    "medium": "Medium",
    "another": "Medium",
    "trick": "Medium",
    "standard": "Medium",
    "difficult": "Medium",
    "hard": "Hard",
    "ssr": "Hard",
    "maniac": "Hard",
    "heavy": "Hard",
    "smaniac": "Challenge",
    "challenge": "Challenge",
    "expert": "Challenge",
    "oni": "Challenge",
    "edit": "Edit",
    # based on community creations
    "challnge": "Challenge",
    "novice": "Beginner",
}


def minimize_measure(measure):  # TODO doesn't work for empty charts
    beats = [b.strip() for b in measure.strip().splitlines()]
    is_minimal = False

    while not is_minimal and len(beats) % 2 == 0:
        even_are_zeros = all(beats[i] == "0" * len(beats[i]) for i in range(1, len(beats), 2))
        if even_are_zeros:
            beats = [beats[i] for i in range(0, len(beats), 2)]
        else:
            is_minimal = True

    return beats


def format_float(float_string):
    f = float(float_string)

    # original rounding formula from SL-ChartParser.lua
    mult = 1000
    rounded = (f * mult + 0.5 - (f * mult + 0.5) % 1) / mult

    return f"{rounded:.3f}"


def normalize_bpms(raw_bpms):
    normalized = []
    beats_bpms = raw_bpms.strip().strip(",").split(",")
    for beat_bpm in beats_bpms:
        beat, bpm = beat_bpm.split("=")
        normalized.append(f"{format_float(beat)}={format_float(bpm)}")

    return ",".join(normalized)


def process_chart(sim, chart, path) -> Chart | None:
    notes = chart.notes
    measures = [m.strip() for m in notes.split(",")]
    minimized_chart = []

    for measure in measures:
        if not measure:  # can happen when file ends with `,;`
            continue
        minimized_measure = minimize_measure(measure)
        minimized_chart.extend(minimized_measure)
        minimized_chart.append(",")
    try:
        minimized_chart_string = "\n".join(minimized_chart[:-1])
        raw_bpms = (getattr(chart, "bpms", None) or sim.bpms).replace("\n", "")
        bpms = normalize_bpms(raw_bpms)
        hash_v3 = sha1((minimized_chart_string + bpms).encode(), usedforsecurity=False).hexdigest()[:16]
    except Exception as e:
        print(f"{path}: Failed to process chart: {e}")
        return None

    try:
        pack_name = path.parent.parent.name.encode("utf-8", "ignore").decode("utf-8")

        # there are some non-integer meters in the wild, StepMania fallbacks to 1
        try:
            diff_number = int(float(chart.meter)) if chart.meter else 1
        except ValueError as e:
            print(f"{path}: Failed to process meter, falling back to 1: {e}")
            diff_number = 1

        return Chart(
            **{
                "subtitletranslit": sim.subtitletranslit or "",
                "diff": DIFF_MAPPING.get(chart.difficulty.lower(), "Edit"),
                "titletranslit": sim.titletranslit or "",
                "artisttranslit": sim.artisttranslit or "",
                "pack_name": pack_name,
                "hash": hash_v3,
                "title": sim.title or "(unknown title)",
                "diff_number": diff_number,
                "artist": sim.artist or "(unknown artist)",
                "subtitle": sim.subtitle or "",
                "steps_type": chart.stepstype,
                "packs": {pack_name},
            }
        )
    except Exception as e:
        print(f"{path}: Failed to process chart: {e}")
        raise


def _get_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Path(s) to chart or pack (a recursive search will be performed in this case)",
        metavar="PATH",
    )
    parser.add_argument(
        "--verify-with-v1-db",
        type=Path,
        help="When the path to v1 db is provided, new metadata will be compared against it",
    )
    parser.add_argument(
        "--workers",
        "-j",
        type=int,
        default=len(os.sched_getaffinity(0)),
        help="Number of workers to use to parallelize the workload",
    )
    parser.add_argument("--db", type=Path, default=Path("db_v2"), help="Path to the output db directory")
    parser.add_argument(
        "--db-driver", choices=STORAGE_DRIVERS, default="lazy", help="Driver for interacting with the db"
    )

    return parser


def load_simfile(p: Path) -> simfile.Simfile | None:
    try:
        sim = simfile.open(str(p))
    except Exception as e:
        print(f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}: Failed to parse in strict mode: {e}")
        try:
            sim = simfile.open(str(p), strict=False)
        except Exception as e:  # can be an SSC with .sm suffix...
            print(f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}: Failed to parse in non-strict mode: {e}")
            try:
                sim = simfile.SSCSimfile(file=StringIO(p.read_text()), strict=False)
            except Exception as e:
                print(f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}: Failed to parse as SSC: {e}")
                print(
                    f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}: Attempting to reject lines with garbled data..."
                )
                raw_bytes = p.read_bytes().replace(b"\xfe\xff", b"")
                split_bytes = raw_bytes.split(b"\n")
                processed_split_lines = []
                for b in split_bytes:
                    for encoding in simfile.ENCODINGS:
                        try:
                            decoded = b.decode(encoding)
                            processed_split_lines.append(decoded)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        print(f"Can't decode line {b}, skipping it")

                processed = "\n".join(processed_split_lines)
                try:
                    sim = simfile.load(StringIO(processed), strict=False)
                except Exception as e:  # give up
                    print(f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}: Giving up because of: {e}")
                    return None

    return sim


def process_sim(p: Path, v1_db, mismatches, storage: StorageV2):
    sim = load_simfile(p)
    if sim is None:
        return

    charts = []
    for chart in sim.charts:
        # in lua we only supported: dance-{single,double,solo,routine,couple}
        if not chart.stepstype.startswith("dance") or chart.stepstype == "dance-threepanel":
            mismatches[f"skipped steps type {chart.stepstype}"] += 1
            continue

        if not chart.notes:
            mismatches[f"no notes {chart.difficulty}"] += 1
            continue

        j = process_chart(sim, chart, p)
        if not j:
            continue

        charts.append(j)

        if not v1_db:
            continue

        reference = get_v1_reference(v1_db, j.hash)

        if not reference:
            if chart.difficulty == "Edit":
                # see https://github.com/florczakraf/stepmania-chart-db-generator/issues/2
                mismatches["missing_edit"] += 1
            elif not chart.difficulty.istitle():
                # see https://github.com/florczakraf/stepmania-chart-db-generator/issues/4
                mismatches[f"missing non-canonical difficulty {chart.difficulty}"] += 1
            elif len(chart) < 7:
                # see https://github.com/florczakraf/stepmania-chart-db-generator/issues/5
                mismatches["missing NOTES props"] += 1
            else:
                print(f"{p}: missing reference for {chart.stepstype} {chart.difficulty} {j.hash}")
                mismatches["missing_reference"] += 1

            continue

        buf = ""
        n_mismatches = 0

        if reference and j != reference:
            for k in reference.keys():
                ref = reference[k]
                new = getattr(j, k)
                if ref != new:
                    if k in (
                        "diff_number",  # usually happens in case of DDR/X/ITG mismatches
                        "pack_name",
                        "subtitle",  # sometimes used for tech
                        "diff",  # tournaments started to change this so that all songs align nicely
                    ):
                        mismatches[k] += 1
                        continue

                    if k == "steps_type":
                        if sorted([ref, new]) == sorted(["dance-couple", "dance-double"]):
                            mismatches["couple/double"] += 1
                            continue

                    if k in (
                        "title",
                        "directory",
                        "artist",
                        "titletranslit",
                        "artisttranslit",
                    ):
                        ref = ref.lower().replace("[", "(").replace("]", ")").replace("~", "-")
                        new = new.lower().replace("[", "(").replace("]", ")").replace("~", "-")

                        if (ref in new) or (
                            new in ref
                        ):  # usually happens in case of prefixing with tiers in tournaments or "feat."
                            mismatches["contains_" + k] += 1
                            continue
                        if k == "directory":
                            mismatches[k] += 1
                            continue

                    n_mismatches += 1
                    buf += f"\t{k}:\n"
                    buf += f"\t\tRef: {ref}\n"
                    buf += f"\t\tNew: {new}\n"
                    buf += "\n"

        if n_mismatches > 1:  # we can live with one mismatch if other stuff matches
            print(f"{str(p).encode('utf-8', 'ignore').decode('utf-8')}:")
            print(buf)

        mismatches[f"n_mismatches {n_mismatches}"] += 1

    storage.add_song(charts)


def main():
    parser = _get_parser()
    args = parser.parse_args()

    expanded_paths = set()
    for path in args.paths:
        p = Path(path)
        if p.is_dir():
            sms = p.rglob("*.[sS][mM]")
            sscs = p.rglob("*.[sS][sS][cC]")
            expanded_paths.update(sms)
            expanded_paths.update(sscs)
        else:
            expanded_paths.add(p)

    mismatches = Counter()

    if args.db.exists():
        print(f"Loading database from: {args.db}")
        driver = STORAGE_DRIVERS[args.db_driver]
        storage = driver.from_disk(args.db)

        print("Packs:", storage.num_packs)
        print("Charts:", storage.num_charts)
    else:
        storage = InMemStorage()

    process_sim_stub = partial(
        process_sim,
        v1_db=args.verify_with_v1_db,
        mismatches=mismatches,
        storage=storage,
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        with tqdm.tqdm(total=len(expanded_paths)) as progress:
            futures = executor.map(process_sim_stub, expanded_paths)
            for _ in futures:
                progress.update()

    storage.to_disk(args.db)

    if args.verify_with_v1_db:
        pprint(mismatches)


if __name__ == "__main__":
    main()

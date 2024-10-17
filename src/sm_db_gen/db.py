import datetime
import json
from collections import defaultdict
from contextlib import suppress
from pathlib import Path


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return sorted(obj)
        return json.JSONEncoder.default(self, obj)


class Chart:
    __slots__ = (
        "title",
        "titletranslit",
        "artist",
        "artisttranslit",
        "subtitle",
        "subtitletranslit",
        "steps_type",
        "diff",
        "diff_number",
        "pack_name",
        "hash",
        "packs",
        "diffs",
    )

    def __init__(self, **kwargs):
        set_attributes = ("packs", "diffs")

        for k, v in kwargs.items():
            if k in set_attributes:
                v = set(v)
            setattr(self, k, v)

    def to_json(self):
        return json.dumps(
            {k: getattr(self, k) for k in self.__slots__},
            cls=SetEncoder,
            sort_keys=True,
        )


class StorageV2:
    def get_chart(self, hash_v3: str) -> Chart | None:
        raise NotImplementedError

    def add_song(self, charts: list[Chart]):
        raise NotImplementedError

    def get_charts(self, pack: str):
        raise NotImplementedError

    @property
    def num_charts(self) -> int:
        raise NotImplementedError

    @property
    def num_packs(self) -> int:
        raise NotImplementedError

    @property
    def last_update(self) -> datetime.datetime:
        raise NotImplementedError


class InMemStorage(StorageV2):
    def __init__(self):
        self._packs = defaultdict(set)
        self._charts = {}
        self._last_update = datetime.datetime.now(tz=datetime.timezone.utc)
        self._touched_charts = set()
        self._touched_packs = set()

    @property
    def num_charts(self) -> int:
        return len(self._charts)

    @property
    def num_packs(self) -> int:
        return len(self._packs)

    @property
    def last_update(self) -> datetime.datetime:
        return self._last_update

    @classmethod
    def from_disk(cls, path: Path) -> "InMemStorage":
        storage = cls()

        metadata = json.loads((path / "metadata.json").read_text())
        storage._last_update = datetime.datetime.fromisoformat(metadata["last_update"])

        for pack_file in (path / "packs").glob("*.json"):
            charts = json.loads(pack_file.read_text())
            storage._packs[pack_file.stem].update(charts)

        for chart_file in (path / "charts").rglob("*.json"):
            chart = Chart(**json.loads(chart_file.read_text()))
            storage._charts[chart.hash] = chart

        if metadata["num_charts"] != len(storage._charts):
            raise ValueError(
                f"Inconsistent number of charts! Loaded {len(storage._charts)} from disk, but expected {metadata['num_charts']}"
            )

        if metadata["num_packs"] != len(storage._packs):
            raise ValueError(
                f"Inconsistent number of packs! Loaded {len(storage._packs)} from disk, but expected {metadata['num_packs']}"
            )

        return storage

    def to_disk(self, path: Path):
        packs_dir = path / "packs"
        packs_dir.mkdir(exist_ok=True, parents=True)

        charts_dir = path / "charts"
        charts_dir.mkdir(exist_ok=True, parents=True)

        print(f"Saving {len(self._touched_packs)}/{self.num_packs} packs")
        for pack in self._touched_packs:
            charts = self._packs[pack]
            (packs_dir / f"{pack}.json").write_text(json.dumps(list(charts), sort_keys=True))

        print(f"Saving {len(self._touched_charts)}/{self.num_charts} charts")
        for hash in self._touched_charts:
            chart = self._charts[hash]
            chart_subdir = charts_dir / f"{hash[:2]}"
            chart_subdir.mkdir(exist_ok=True, parents=True)

            (chart_subdir / f"{hash[2:]}.json").write_text(chart.to_json())

        (path / "metadata.json").write_text(
            json.dumps(
                {
                    "last_update": self._last_update.isoformat(),
                    "num_charts": len(self._charts),
                    "num_packs": len(self._packs),
                },
                sort_keys=True,
                indent=2,
            )
        )

    def get_chart(self, hash_v3: str) -> Chart | None:
        return self._charts.get(hash_v3)

    def add_song(self, charts: list[Chart]):
        self._last_update = datetime.datetime.now(tz=datetime.timezone.utc)

        diffs = {c.hash for c in charts}
        self._touched_charts.update(diffs)

        for chart in charts:
            chart.diffs = diffs
            hash = chart.hash
            pack_name = chart.pack_name
            self._touched_packs.add(pack_name)
            self._packs[pack_name].add(hash)

            if hash in self._charts:
                self._charts[hash].packs.add(pack_name)
                self._charts[hash].diffs.update(diffs)
            else:
                self._charts[hash] = chart

    def get_charts(self, pack: str) -> list[Chart]:
        return [self._charts[hash] for hash in self._packs[pack]]


class LazyStorage(StorageV2):
    def __init__(self):
        self._packs = defaultdict(set)
        self._charts = {}
        self._last_update = None
        self._location = None

        self._num_disk_packs = 0
        self._num_disk_charts = 0

    # these are just a guesstimates until we save
    @property
    def num_charts(self) -> int:
        return self._num_disk_charts + len(self._charts)

    @property
    def num_packs(self) -> int:
        return self._num_disk_packs + len(self._packs)

    @property
    def last_update(self):
        return self._last_update

    @classmethod
    def from_disk(cls, path: Path) -> "LazyStorage":
        storage = cls()

        storage._location = path

        metadata = json.loads((path / "metadata.json").read_text())
        storage._last_update = datetime.datetime.fromisoformat(metadata["last_update"])
        storage._num_disk_charts = metadata["num_charts"]
        storage._num_disk_packs = metadata["num_packs"]

        return storage

    def to_disk(self, path: Path):
        new_packs = 0
        new_charts = 0

        packs_dir = path / "packs"
        packs_dir.mkdir(exist_ok=True, parents=True)

        charts_dir = path / "charts"
        charts_dir.mkdir(exist_ok=True, parents=True)

        print(f"Saving {len(self._packs)} packs")
        for pack, charts in self._packs.items():
            new_packs += 1
            with suppress(IOError):
                disk_charts = json.loads((packs_dir / f"{pack}.json").read_text())
                charts.update(disk_charts)
                new_packs -= 1

            (packs_dir / f"{pack}.json").write_text(json.dumps(list(charts), sort_keys=True))

        print(f"Saving {len(self._charts)} charts")
        for hash, chart in self._charts.items():
            new_charts += 1
            chart_subdir = charts_dir / f"{hash[:2]}"
            chart_subdir.mkdir(exist_ok=True, parents=True)
            chart_path = chart_subdir / f"{hash[2:]}.json"

            with suppress(IOError):
                disk_chart = Chart(**json.loads(chart_path.read_text()))
                # keep original data, only extend packs/diffs
                disk_chart.packs.update(chart.packs)
                disk_chart.diffs.update(chart.diffs)
                chart = disk_chart
                new_charts -= 1

            chart_path.write_text(chart.to_json())

        print(f"Saved {new_charts} new charts and {new_packs} new packs")

        self._num_disk_packs += new_packs
        self._num_disk_charts += new_charts

        (path / "metadata.json").write_text(
            json.dumps(
                {
                    "last_update": self._last_update.isoformat(),
                    "num_charts": self._num_disk_charts,
                    "num_packs": self._num_disk_packs,
                },
                sort_keys=True,
                indent=2,
            )
        )

        self._charts.clear()
        self._packs.clear()

    def get_chart(self, hash_v3: str) -> Chart | None:
        if self._charts:
            raise RuntimeError(f"{len(self._charts)} pending changes, please call to_disk first.")

        chart_path = self._location / "charts" / f"{hash_v3[:2]}" / f"{hash_v3[2:]}.json"
        try:
            return Chart(**json.loads(chart_path.read_text()))
        except IOError:
            return None

    def add_song(self, charts: list[Chart]):
        self._last_update = datetime.datetime.now(tz=datetime.timezone.utc)

        diffs = {c.hash for c in charts}

        for chart in charts:
            chart.diffs = diffs
            hash = chart.hash
            pack_name = chart.pack_name
            self._packs[pack_name].add(hash)

            if hash in self._charts:
                self._charts[hash].packs.add(pack_name)
                self._charts[hash].diffs.update(diffs)
            else:
                self._charts[hash] = chart


STORAGE_DRIVERS = {
    "inmem": InMemStorage,
    "lazy": LazyStorage,
}

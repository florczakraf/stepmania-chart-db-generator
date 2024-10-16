import json
from pathlib import Path


def get_v1_reference(v1_db_root: Path, hash_v3: str) -> dict | None:
    """V1 of the chart db database used the following 2-level file-system layout:
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

    """

    reference_path = v1_db_root / hash_v3[:2] / f"{hash_v3[2:]}.json"

    if not reference_path.exists():
        return None

    # see rationale behind replace: https://github.com/florczakraf/stepmania-chart-db-generator/issues/3
    return json.loads(reference_path.read_bytes().decode("utf8", errors="replace").replace("\\\\", ""))

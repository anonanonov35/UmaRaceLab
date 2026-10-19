"""Validated, local-only course geometry extracted from the user's own Unity assets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import os


def cache_path(database: Path) -> Path:
    key = hashlib.sha256(str(database.resolve()).encode()).hexdigest()[:16]
    base=Path(os.environ['UMA_LAB_CACHE_DIR']) if os.environ.get('UMA_LAB_CACHE_DIR') else Path(tempfile.gettempdir())/'uma-race-lab'
    return base / key / "courses-v1.json"


class CourseCatalog:
    def __init__(self, database: Path, database_fingerprint:str|None=None):
        self.database = database
        self.payload = None
        path = cache_path(database)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError,OSError):
                return
            meta = database.parent.parent / "meta"
            if meta.exists():
                stat = meta.stat()
                fingerprint=database_fingerprint or hashlib.sha256(database.read_bytes()).hexdigest()
                if payload.get('schema')==2 and payload.get('database_sha256')==fingerprint and payload.get("index_signature") == [stat.st_size, stat.st_mtime_ns]:
                    self.payload = payload

    def get(self, course_id: int) -> dict:
        if not self.payload or str(course_id) not in self.payload["courses"]:
            raise ValueError("Нет проверенной локальной геометрии трассы. Запустите tools/build_course_catalog.py для своей установки.")
        geometry = self.payload["courses"][str(course_id)]
        if geometry.get("error"):
            raise ValueError(f"Геометрия #{course_id}: {geometry['error']}")
        return geometry

    @property
    def parameters(self) -> dict:
        return self.payload["parameters"] if self.payload else {}


def position_at(geometry: dict, distance: float) -> tuple[float, float, float]:
    points = geometry["points"]
    coordinate = max(0., min(1., distance / geometry["distance"])) * (len(points) - 1)
    i = min(int(coordinate), len(points) - 2)
    part = coordinate - i
    return tuple(points[i][a] + (points[i+1][a] - points[i][a]) * part for a in range(3))


def segment_at(segments: list[dict], distance: float) -> dict | None:
    return next((s for s in segments if s["start"] <= distance < s["start"] + s["length"]), None)


def world_position_at(geometry:dict,distance:float,lane:float,turn:int) -> tuple[float,float,float]:
    x,z,height=position_at(geometry,distance)
    rotations=geometry.get('rotations')
    if rotations:
        t=max(0,min(1,distance/geometry['distance']))*(len(rotations)-1)
        i=min(int(t),len(rotations)-2);part=t-i
        a,b=rotations[i],rotations[i+1]
        sign=-1 if sum(u*v for u,v in zip(a,b))<0 else 1
        q=[u+(sign*v-u)*part for u,v in zip(a,b)]
        norm=sum(v*v for v in q)**.5
        q=[v/norm for v in q]
        right=(1-2*(q[1]**2+q[2]**2),2*(q[0]*q[2]-q[3]*q[1]))
    else:
        a,b=position_at(geometry,max(0,distance-1)),position_at(geometry,min(geometry['distance'],distance+1))
        dx,dz=b[0]-a[0],b[1]-a[1];norm=(dx*dx+dz*dz)**.5 or 1
        right=(dz/norm,-dx/norm)
    side=-1 if turn==1 else 1
    return x+side*right[0]*lane,z+side*right[1]*lane,height


def phase_marks(distance: float) -> list[tuple[str, float, float]]:
    return [("early race", 0., distance / 6), ("mid race", distance / 6, distance * 2/3),
            ("late race", distance * 2/3, distance * 5/6), ("last spurt", distance * 5/6, distance)]

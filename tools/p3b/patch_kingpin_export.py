"""One-off (P3b, D-051): the wheel definition carries its kingpin (the two ball joints) for the front alignment element."""
from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("tools/blender/hcar/sk.py", [(
    '''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=(), windup="", windup_body=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036); windup: wind-up element
        parameter set, windup_body: the body nodes of its couple (D-036)."""''',
    '''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=(), windup="", windup_body=(), kingpin=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036); windup: wind-up element
        parameter set, windup_body: the body nodes of its couple (D-036); kingpin: the lower and the upper ball joint of a
        steered knuckle (the steering axis of the alignment element, D-051)."""'''), (
    '''                            "windup": windup, "windupBody": [self.idx(n) for n in windup_body]})''',
    '''                            "windup": windup, "windupBody": [self.idx(n) for n in windup_body],
                            "kingpin": [self.idx(n) for n in kingpin]})''')])
patch("tools/blender/hcar/hskel.py", [(
    '''        wheels[name] = dict(w, arm=tre, lsh=lbj, arb_pick=lbj, part=part, lca=(li_f, li_r))''',
    '''        wheels[name] = dict(w, arm=tre, lsh=lbj, arb_pick=lbj, part=part, lca=(li_f, li_r), kingpin=(lbj, ubj))'''), (
    '''                   drive_reaction=() if front else st["diff"], windup="front" if front else "rear",
                   windup_body=windup_body(B, name))''',
    '''                   drive_reaction=() if front else st["diff"], windup="front" if front else "rear",
                   windup_body=windup_body(B, name), kingpin=w.get("kingpin", ()))''')])
patch("Unity/HellcatSandbox/Assets/Sim/Data/VehicleDef.cs", [(
    '''        public int[] windupBody;     // body nodes taking the wind-up couple (link pivots, their mounts, the spring tower)''',
    '''        public int[] windupBody;     // body nodes taking the wind-up couple (link pivots, their mounts, the spring tower)
        public int[] kingpin;        // steered knuckles: lower and upper ball joint (alignment element's camber axis, D-051)''')])
print("patched")

import io
p = r"W:/YouTube/3D Model Dodge Challenger/tools/p6/sweep.py"
s = io.open(p, encoding="utf-8").read()
a = '''        if not ns.collect:
            run(sc, kmh, "baseline", None, logs / f"{sc}_baseline.log")
'''
b = '''        if not ns.collect:
            # the baseline reads the same file as the variants (sim/vehicle/hellcat/params.json now, not the build's copy)
            pb = pdir / "params_baseline.json"
            pb.write_text(PARAMS.read_text(encoding="utf-8"), encoding="utf-8")
            run(sc, kmh, "baseline", pb, logs / f"{sc}_baseline.log")
'''
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

import io
p = r"W:/YouTube/3D Model Dodge Challenger/tools/gate_p6.py"
s = io.open(p, encoding="utf-8", newline="").read()
a = s[s.index('    s3 = by.get(("S3", 50))'):s.index('    for sc in ("S4", "S6"):')]
b = '''    s3 = by.get(("S3", 50))
    if s3 and r50:
        # the pole goes between the rails: the bumper beam's middle is driven back far deeper than any point of the
        # full-width crash at the same speed, and the cabin travels further before it stops
        deep = s3["max_deformation_m"] > 1.5 * r50["max_deformation_m"] and (s3["dynamic_crush_m"] or 0) > (r50["dynamic_crush_m"] or 0)
        check("S3 centred pole at 50 km/h: deep intrusion - the pole drives the front in far deeper than the full-width wall at the same "
              "speed (brief 9)", "PASS" if deep else "FAIL",
              f"deepest point {fmt(s3['max_deformation_m'])} m ({s3['max_deformation_node']}) vs {fmt(r50['max_deformation_m'])} m in S1 50; "
              f"cabin travel {fmt(s3['dynamic_crush_m'])} vs {fmt(r50['dynamic_crush_m'])} m; plastic {s3['plastic_kJ']} vs {r50['plastic_kJ']} kJ; "
              f"intrusion {intrusion_text(s3)}")
'''
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")

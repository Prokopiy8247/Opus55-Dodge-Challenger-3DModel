# NHTSA NCAP frontal test: 2013 Dodge Challenger SXT (report NCAP-MGA-2013-030)

Source: https://nrd-static.nhtsa.dot.gov/reports/vehdb/v00000/v08000/v08048R001.pdf (public U.S. DOT report, MGA Research,
test date 2012-11-08; the PDF is not kept in git). `text_all.txt` is its text extracted with pypdf (tools/p6/pdf_text.py).

Values used for the P6 calibration (brief 15.2), data sheet no. 13 / 14:

| item | value |
|---|---|
| test weight | 1947.8 kg |
| impact velocity | 56.4 km/h (rigid full-width barrier) |
| velocity change / time of separation | 66.0 km/h / 134.2 ms (rebound 9.6 km/h = 2.67 m/s) |
| static crush profile C1..C6 (bumper level) | 573, 607, 642, 639, 611, 573 mm (mean 608 mm) |
| maximum static crush (centre line) | 740 mm |
| wheelbase change left / right | 155 / 149 mm shorter |
| door opening width change | 1 to 6 mm |
| doors | closed during the impact, operable afterwards |

Also: 2009 Dodge Challenger SE (NCAP-MGA-2009-002, https://nrd-static.nhtsa.dot.gov/reports/vehdb/v00000/v06500/v06532R001.pdf):
56.5 km/h, maximum post-test static crush 632 mm.

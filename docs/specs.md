# Dodge Challenger SRT Hellcat Widebody: specification sheet

Target car: 2019–2023 Challenger SRT Hellcat Widebody (717 hp), left-hand drive. These numbers feed the Blender model and the Unity soft-body sandbox. Compiled 2026-10-11 from public sources only. Every value has a source ID, and section 0 maps each ID to its URL.

**Tags:**
- [OFFICIAL]: Dodge/FCA spec sheet or press release.
- [TEST]: instrumented magazine test.
- [2ND]: secondary source (aggregator, forum, dealer option list). Treat as unverified.
- [DERIVED]: computed here from sourced numbers.
- [EST]: engineering estimate, not published anywhere.

**Trim flags:**
- WB: SRT Hellcat Widebody, the target.
- STD: standard-body SRT Hellcat.
- RE: Hellcat Redeye.
- SPWB: R/T Scat Pack Widebody.
- MY18: 2018 Hellcat Widebody (707 hp).

Where a source gives both inches and millimetres, both are copied. Values in [brackets] are converted or computed here.

> **Model-year flag (affects the engine and mass numbers).** The hood in `reference/2.jpg` has one centred mesh scoop and two heat extractors near the cowl. That is the 2015–2018 Hellcat hood: Dodge's Widebody launch release lists a "Power-bulge aluminum hood with center intake and dual heat extractors" [S7].
> - For MY2019, all Challenger SRT Hellcats got "a new fully functional, dual-snorkel hood" [S9]; see also [S8][S19].
> - The old hood moved to the R/T Scat Pack [S9].
> - The grille badge in the photo is SRT plus a Hellcat head, not a Scat Pack badge.
>
> So the photographed car is most likely a **MY2018 Hellcat Widebody (707 hp / 650 lb-ft)**, or a 2019+ Hellcat with a non-original hood. Body dimensions, tires, Cd, steering and suspension are the same for 2018 and 2019–2023; section 1.1 lists the differences. The values below follow the requested 717-hp generation.

## Summary of recommended values

| Group | Parameter | Recommended (metric) | Imperial | Source | Note |
|---|---|---|---|---|---|
| Dimensions | Overall length | 5,017 mm | 197.5 in | S1–S5 | same as STD Hellcat |
| | Width without mirrors (at front flares) | 1,990 mm | 78.3 in | S1–S6 | press says the flares add 3.5 in; the spec sheets differ by 2.6 in |
| | Width with mirrors | 2,169 mm | 85.4 in | S1–S5 | no trim qualifier in the sheets |
| | Height | 1,460 mm | 57.5 in | S1–S6 | sheets: 1,459.8 (2018–19), 1,461 (2020–23) |
| | Wheelbase | 2,950 mm | 116.2 in | S1, S6 | 2020–23 sheets round to 116 in (2,946 mm) |
| | Front track | 1,667 mm | 65.6 in | S1–S6 | STD Hellcat 1,625 mm (64.0 in) |
| | Rear track | 1,669 mm | 65.7 in | S1–S6 | sheets print "(1,618)" mm, a copy error; STD 1,618 mm (63.7 in) |
| | Overhang, front + rear | 2,067 mm total | [81.4 in] | DERIVED | front/rear split not published |
| | Ground clearance | 115 mm | 4.5 in | S1–S6 | |
| | Approach / departure / breakover angles | not published | | – | |
| | STD width (at doors), for comparison | 1,923 mm | 75.7 in | S1–S6 | |
| Mass | Curb weight, automatic | 2,030 kg | 4,476 lb | S1, S2 | 2021: 2,034 kg; 2022–23: 2,029 kg; MY18: 2,040 kg |
| | Curb weight, manual | 2,028 kg | 4,470 lb | S1, S2 | 2021: 2,032 kg; 2022–23: 2,017 kg; MY18: 2,037 kg |
| | Weight distribution F/R | 57 / 43 % | | S1–S6, S11 | Dodge figure has no WB row; C&D measured 56.7 % front |
| | Fuel tank | 70.0 L | 18.5 US gal | S1–S6 | |
| Wheels, tires | Tires | 305/35ZR20 (107Y), all four corners | | S1–S5, S11 | Pirelli P Zero |
| | Effective rolling radius | [350 mm] | | DERIVED (731 rev/mile) | nominal unloaded diameter [721.5 mm] |
| | Wheels | 20 × 11 in, all four corners | | S1–S8 | |
| | Wheel offset | ET −2.5 mm | | S20 [2ND] | unverified |
| Brakes | Front | Brembo 6-piston fixed monoblock; two-piece rotor, vented and slotted: 390 × 34 mm (2019–20), 400 × 34 mm (2021–23) | 15.4 / 15.7 in | S1–S5 | |
| | Rear | Brembo 4-piston fixed; rotor 350 × 28 mm, vented | 13.8 in | S1–S5 | |
| | Caliper colors | red (standard); black, gunmetal gray, orange (options) | | S19; red: S21 [2ND] | |
| Engine | Power | 535 kW @ 6,000 rpm | 717 bhp | S1–S5 | MY18: 527 kW (707 bhp) @ 6,000 |
| | Torque | 889 N·m @ 4,800 rpm | 656 lb-ft | S1–S5 | MY18: 881 N·m (650 lb-ft) @ 4,800 |
| | Max engine speed (fuel cut-off) | 6,200 rpm | | S1–S6, S8, S11 | |
| | Boost, maximum | 80 kPa | 11.6 psi | S8, S10 | |
| | Low-rpm torque | 557 N·m @ 1,200 rpm | 411 lb-ft | S16 | chief-engineer quote, 707-hp engine |
| | Idle speed | not published | | – | |
| Driveline | 8HP90 ratios, gears 1–8 | 4.714 / 3.143 / 2.106 / 1.667 / 1.285 / 1.000 / 0.839 / 0.667 | | S15 | Dodge rounds to two decimals |
| | Reverse | 3.317 | | S15 | Dodge: 3.32 (S1–S5), 3.30 (S10) |
| | Final drive, automatic | 2.62 : 1 | | S1–S5, S10 | |
| | TR-6060 manual, gears 1–6 and R | 2.26 / 1.58 / 1.19 / 1.00 / 0.77 / 0.63, R 2.90 | | S1–S6 | |
| | Final drive, manual | 3.70 : 1 | | S1–S6 | |
| | Differential | asymmetric limited-slip, 230 mm axle | | S1–S5, S10 | mechanism and bias ratios not published |
| Performance | 0–60 mph | 3.8 s (tested) | | S11 | MY18 WB automatic; Dodge claims 3.4 s |
| | 0–100 km/h | ≈ 3.9–4.0 s | | EST | no instrumented test found |
| | Quarter mile | 11.8 s @ [203 km/h] | 126 mph | S11 | Dodge claims 10.9 s @ 127 mph |
| | Top speed | [314 km/h] | 195 mph | S7, S8 | STD 199 mph |
| | Braking, 70–0 mph | [46.9 m] | 154 ft | S11 | [≈ 37 m] from 100 km/h (DERIVED) |
| | Skidpad | 0.95 g | | S11 | 300-ft skidpad; Dodge claims 0.97 g |
| Chassis | Front suspension | SLA with high upper A-arm, lateral and diagonal lower links, coil-over Bilstein adaptive dampers, 34 mm anti-roll bar | | S1–S6 | |
| | Rear suspension | five-link independent, coil springs, Bilstein adaptive dampers, 22 mm anti-roll bar | | S1–S6 | 22 mm is specific to WB |
| | Spring rates | not published | | – | |
| | Steering | EPS, ratio 14.4 : 1, 2.5 turns lock to lock | | S1–S7 | 2.52 turns in the 2018–19 sheets |
| | Turning circle, curb to curb | [11.80 m] | 38.7 ft | S1–S6 | |
| | Road-wheel angle at lock | [≈ 31° mean] | | DERIVED | |
| Aero | Cd | 0.398 | | S1–S6 | STD 0.382 |
| | Frontal area | [2.49 m²] | 26.8 sq ft | S2–S5 | STD [2.42 m²] |
| | CdA | [0.99 m²] | | DERIVED | |
| Driver | Eye height above ground | ≈ 1.16 m ± 0.05 m | | EST (section 9) | H-point not published |

## 0. Sources

| ID | Source | URL |
|---|---|---|
| S1 | Dodge/FCA, 2019 Dodge Challenger / Challenger SRT Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2019_DG_Challenger_ChallengerSRT_SP.pdf |
| S2 | Dodge/FCA, 2020 Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2020_DG_Challenger_ChallengerSRT_SP.pdf |
| S3 | Dodge/FCA, 2021 Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2021_DG_Challenger_ChallengerSRT_SP.pdf |
| S4 | Dodge/FCA, 2022 Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2022_DG_Challenger_ChallengerSRT_SP.pdf |
| S5 | Dodge/FCA, 2023 Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2023_DG_Challenger_ChallengerSRT_SP.pdf |
| S6 | Dodge/FCA, 2018 Specifications (PDF) [OFFICIAL] | https://s3.amazonaws.com/chryslermedia.iconicweb.com/mediasite/specs/2018_DG_Challenger_ChallengerSRT_SP.pdf |
| S7 | Dodge press release, "New Challenger SRT Hellcat Widebody Completes Dodge's Most Powerful Muscle Car Lineup Ever for 2018", 27 Jun 2017 [OFFICIAL] | https://media.stellantisnorthamerica.com/newsrelease.do?id=18423 |
| S8 | Dodge press release, "New 2019 Dodge Challenger SRT Hellcat Redeye: Possessed by the Demon" (2019 lineup, includes the performance table) [OFFICIAL] | https://media.stellantisnorthamerica.com/newsrelease.do?id=19970 |
| S9 | Dodge, "2019 Dodge Challenger / Challenger SRT Fact Sheet" [OFFICIAL] | https://media.stellantisnorthamerica.com/newsrelease.do?id=19986 |
| S10 | Dodge press release on the 2015 Charger SRT Hellcat powertrain (same engine, transmission and axle) [OFFICIAL] | https://media.stellantisnorthamerica.com/newsrelease.do?id=16139 |
| S11 | Car and Driver, "Tested: 2018 Dodge Challenger SRT Hellcat Widebody Manual", Jul 2018 [TEST] | https://www.caranddriver.com/reviews/a22026777/2018-dodge-challenger-hellcat-widebody-manual-test-review/ |
| S12 | Car and Driver, Challenger SRT Hellcat review page; its test box is for a 2019 Hellcat Redeye Widebody [TEST] | https://www.caranddriver.com/dodge/challenger-srt-srt-hellcat |
| S13 | Car and Driver, "Tested: 2016 Dodge Challenger Hellcat Automatic" (STD) [TEST] | https://www.caranddriver.com/reviews/a15100533/2016-dodge-challenger-srt-hellcat-automatic-test-review/ |
| S14 | FastestLaps, Challenger SRT Hellcat page; a user comment quotes Motor Trend's 7/2018 test of a 2018 Hellcat Widebody automatic [2ND] | https://fastestlaps.com/models/dodge-challenger-srt-8-hellcat |
| S15 | ZF, 8HP 90 S / 90 SX technical data sheet (standard ratios) | https://www.zf.com/products/media/industrial/special_vehicles/brochures_2/ProductOverview_Defence_Technical_Data_Sheets.pdf |
| S16 | autoevolution, "Hellcat V8 Engine Fact - 411 LB-FT from 1,200 RPM" (quotes SRT chief engineer Darryl Smith, 2014) | https://www.autoevolution.com/news/hellcat-v8-engine-fact-411-lb-ft-from-1200-rpm-video-88379.html |
| S17 | EngineLabs, "SRT Engineer Explains How Hellcat Hemi Pulls 707 Horsepower" | https://www.enginelabs.com/news/hellcat-hemi-chief-engineer-provides-engine-details/ |
| S18 | dimensions.com, Dodge Challenger SRT Hellcat (3rd Gen), STD body only | https://www.dimensions.com/element/dodge-challenger-srt-hellcat-3rd-gen |
| S19 | MoparInsiders, "2019 Dodge Challenger SRT HELLCAT Options and Pricing" (dealer-order data) [2ND] | https://moparinsiders.com/2019-dodge-challenger-srt-hellcat-options-and-pricing/ |
| S20 | Wheel offset: a challengertalk.com forum thread (seen only as a search excerpt; the page blocks automated access) and an AmericanMuscle replica-wheel listing titled "20x11; -2.5mm Offset (18-23 Challenger Widebody)" [2ND] | https://www.challengertalk.com/threads/widebody-wheel-options.694551/ and https://www.americanmuscle.com/store-brand-challenger-hellcat-widebody-style-matte-black-wheel-20x11-vzn100793.html |
| S21 | Caliper colors: owner-forum threads, seen only as search excerpts (the pages block automated access) [2ND] | https://www.hellcat.org/threads/what-color-is-your-caliper.232533/ and https://www.challengertalk.com/threads/brembo-calipers-if-dont-select-a-factory-option.667539/ |
| S22 | Stock 717-hp chassis-dyno reports: owner-forum threads, seen only as search excerpts [2ND] | https://www.hellcat.org/threads/dyno-2020-widebody-stock-baseline.244573/ and https://www.challengertalk.com/threads/hellcat-dyno-results.700009/ |

S1–S6 use a two-column layout that text extraction scrambles. Each value was matched label to value and cross-checked across all six model years.

MotorTrend's Widebody test pages could not be located: the site search is script-driven, and the model pages carry only catalog data. No instrumented Widebody test from Road & Track or Edmunds was found.

## 1. Exterior dimensions

| Parameter | in | mm | Applies to | Source | Comment |
|---|---|---|---|---|---|
| Overall length | 197.5 | 5,017 | WB and STD Hellcat ("R/T Scat Pack Widebody, SRT Hellcat models") | S2–S5 | 5,016.5 in S1; 5,015.6 for "Challenger SRT Widebody" in S6; non-SRT Challengers 197.9 in (5,027 mm) |
| Width without mirrors | 78.3 | 1,990 | WB, "at widest point of vehicle, front flares" | S2–S5 | 1,989.9 in S1, S6 |
| Width without mirrors | 75.7 | 1,923 | STD and other non-WB trims, "at widest point of vehicle, doors" | S1–S6 | dimensions.com: 192 cm (S18) |
| Width gain from flares (press figure) | +3.5 | [+89] | WB | S7, S8 | "adding 3.5 inches of width" (S7). The sheets give 78.3 − 75.7 = 2.6 in (66 mm). C&D lists 79.2 in for MY18 (S11, which equals 75.7 + 3.5) and 78.3 in for the RE WB (S12). |
| Width with mirrors | 85.4 | 2,169 | all Challengers (no trim qualifier) | S1–S5 | the mirrors sit outboard of the flares, so the value should also hold for WB |
| Overall height | 57.5 | 1,461 | "SRT Hellcat Widebody" | S2–S5 | 1,459.8 for "Challenger SRT Widebody" in S1, S6; C&D also 57.5 in (S11, S12) |
| Overall height | 57.2 | 1,454 | STD Hellcat | S2–S5 | 57.0 in (1,449.4 mm) in S1, S6 |
| Wheelbase | 116.2 | 2,950.4 | all Challengers | S1, S6 | 116 (2,946) in S2–S5; C&D 116.2 in (S11, S12); dimensions.com 295 cm (S18) |
| Front track | 65.6 | 1,667 | WB and SPWB | S2–S5 | 1,666.9 in S1, S6. C&D: "The Widebody benefits from a 1.7-inch-wider front track" (S11) |
| Front track | 64.0 | 1,625 | STD Hellcat | S1–S6 | non-SRT 63.4 in (1,610 mm) |
| Rear track | 65.7 | [1,669] | WB and SPWB | S1–S6 | every sheet prints "65.7 (1,618)"; the mm value is copied from the STD row, and 65.7 in = 1,668.8 mm |
| Rear track | 63.7 | 1,618 | STD Hellcat | S1–S6 | non-SRT 63.8 in (1,620 mm) |
| Front / rear overhang | – | – | WB | not published | total [2,067 mm] = 5,017 − 2,950 (DERIVED); take the split from the photos |
| Ground clearance | 4.5 | 115.2 | "SRT Hellcat models" (S1–S5), "Challenger SRT Widebody" (S6) | S1–S6 | non-SRT 5.2 in (130.9 mm). The sheets say all dimensions are measured at curb weight on standard tires. |
| Approach / departure / breakover angles | – | – | – | not found | not in any Dodge sheet or magazine test |

Recommendations:
- **Wheelbase 2,950 mm.** The 2018–19 sheets give it to 0.1 mm (116.2 in). The later "116 (2,946)" is the inch figure rounded to a whole number and converted back.
- **Width 1,990 mm.** The sheet value states where it was measured (the front flares). The "3.5 inches" figure comes from a press release and gives no reference point. Confirm with the silhouette overlay.
- **Rear track 1,669 mm.** The inch value is internally consistent: +2.0 in over STD, against +1.6 in at the front. The printed millimetre value is a copy error.

### 1.1 MY2018 vs MY2019–2023 Hellcat Widebody

| Item | MY2018 (707 hp) | MY2019–2020 | MY2021–2023 | Source |
|---|---|---|---|---|
| Engine | 707 bhp (527 kW) @ 6,000; 650 lb-ft (881 N·m) @ 4,800 | 717 bhp (535 kW) @ 6,000; 656 lb-ft (889 N·m) @ 4,800 | same as 2019–20 | S6; S1–S5 |
| Hood | centre intake plus dual heat extractors | dual-snorkel | dual-snorkel | S7; S8, S9, S19 |
| Curb weight, auto / manual | 4,498 / 4,490 lb (2,040 / 2,037 kg) | 4,476 / 4,470 lb (2,030 / 2,028 kg) | 2021: 4,486 / 4,479 lb (2,034 / 2,032 kg); 2022–23: 4,473 / 4,446 lb (2,029 / 2,017 kg) | S6; S1, S2; S3; S4, S5 |
| Front rotors | 390 × 34 mm | 390 × 34 mm | 400 × 34 mm | S6; S1, S2; S3–S5 |
| Standard 20 × 11 wheel | "Devil's Rim" Low Gloss Granite Crystal | 2019: "Devil's Rim"; 2020: Low Gloss Black | Carbon Black | S6; S1, S2; S3–S5 |
| Anti-roll bars, front / rear | 34 mm / 22 mm, solid | 2019: solid; 2020: hollow | hollow | S6; S1, S2; S3–S5 |
| Wheelbase as printed | 116.2 in (2,950.4 mm) | 2019: 116.2 in; 2020: 116 in (2,946 mm) | 116 in (2,946 mm) | S6; S1, S2; S3–S5 |
| Height as printed | 57.5 in (1,459.8 mm) | 2019: 1,459.8 mm; 2020: 1,461 mm | 1,461 mm | S6; S1, S2; S3–S5 |
| Cd | 0.398 | 0.398 | 0.398 | S1–S6 |
| Steering | EPS (the WB only; the MY18 STD Hellcat kept hydraulic assist) | EPS | EPS | S6, S7; S8 |

A satin-black painted hood (code MYW, $1,995) was a factory option on the 2019 Hellcat (S19).

## 2. Mass

| Variant | lb | kg | Source |
|---|---|---|---|
| WB automatic, 2019 and 2020 | 4,476 | 2,030 | S1, S2 |
| WB manual, 2019 and 2020 | 4,470 | 2,028 | S1, S2 |
| WB auto / manual without rear seat, 2019 and 2020 | 4,428 / 4,421 | 2,009 / 2,005 | S1, S2 |
| WB automatic, 2021 | 4,486 | 2,034 | S3 |
| WB manual, 2021 | 4,479 | 2,032 | S3 |
| WB auto / manual without rear seat, 2021 | 4,437 / 4,431 | 2,013 / 2,010 | S3 |
| WB automatic, 2022 and 2023 | 4,473 | 2,029 | S4, S5 |
| WB manual, 2022 and 2023 | 4,446 | 2,017 | S4, S5 |
| WB auto / manual, MY18 | 4,498 / 4,490 | 2,040 / 2,037 | S6 |
| STD Hellcat auto / manual, 2019 | 4,436 / 4,429 | 2,012 / 2,009 | S1 |
| RE WB, 2019 / 2023 | 4,492 / 4,481 | 2,038 / 2,032 | S1, S5 |
| Measured by C&D: MY18 WB manual | 4,538 | [2,058] | S11 |
| Measured by C&D: 2019 RE WB automatic | 4,514 | [2,048] | S12 |
| Measured by C&D: 2016 STD Hellcat automatic | 4,493 | [2,038] | S13 |

**Weight distribution:**
- Dodge lists "57/43 -- SRT Hellcat (manual)" and "57/43 -- SRT Hellcat (automatic)". There is no separate Widebody row (S1–S6).
- Car and Driver, MY18 WB manual: "Despite 56.7 percent of its weight over those front tires" (S11).
- No MotorTrend measurement was found.

**Fuel tank:** 18.5 US gal (70.0 L) (S1–S6).

**Recommendation:** use 2,030 kg curb weight for the automatic. It is Dodge's 2019–20 figure and sits mid-range of the 2,017–2,040 kg spread across model years. Magazine test cars weigh 20–30 kg more, which is probably options. Add the driver separately.
- [DERIVED] At 57/43, the axle loads are [1,157 kg front / 873 kg rear].
- [DERIVED] The CG sits [1,268 mm] behind the front axle.
- CG height is not published.

## 3. Wheels, tires, brakes

### Tires

| Item | Value | Applies to | Source |
|---|---|---|---|
| Size | 305/35ZR20, all four corners | WB, SPWB, RE WB | S1–S8 |
| Standard tire | "305/35ZR20 All-season Performance", Pirelli P Zero (All-season) | WB | S1–S5 |
| Optional tire | same size, Pirelli P Zero three-season (summer). The 2019 option list shows "305/35ZR20 P Zero Summer Tires (TYN) – $695 with Widebody Option" | WB | S1–S5, S19 |
| Load / speed index | 107Y (C&D test car) | MY18 WB | S11 |
| Revs per mile (per km) | 731 (454) | WB | S1–S5 |
| Rolling circumference / effective radius | [2.202 m / 350.4 mm] | WB | DERIVED from 731 rev/mile |
| Nominal unloaded diameter | [721.5 mm] = 508 + 2 × 106.75 | WB | DERIVED from the size code |
| Size on STD Hellcat | 275/40ZR20, 718 rev/mile (446/km); 721 (448) in S1 | STD | S1–S5 |

### Wheels

The size is 20 × 11 in on all four corners (S1–S8); the STD Hellcat uses 20 × 9.5 in (S1–S5). Dodge describes the launch wheel as "20 x 11-inch "Devil's Rim" split-five spoke aluminum wheels" (S7). For 2019 it describes "split-five spoke, 20 x 11-inch "Devil's Rim" forged aluminum wheels" (S8).

| MY | 20 × 11 designs listed for the Hellcat Widebody | Source |
|---|---|---|
| 2018 | "Devil's Rim" Low Gloss Granite Crystal (standard) | S6 |
| 2019 | "Devil's Rim" Low Gloss Granite Crystal (included with SPWB and Hellcat WB) | S1 |
| 2020 | Low Gloss Black (included with the Widebody Package); Low Gloss Granite "Warpspeed" (option); Brass Monkey "Devil's Rim" (option). SPWB: Low Gloss Granite "Devil's Rim" | S2 |
| 2021 | Carbon Black (standard with the Widebody Package); Low Gloss Granite "Warpspeed" (option); Brass Monkey "Devil's Rim" (option) | S3 |
| 2022 | Carbon Black (standard on Hellcat with the Widebody Package); Low Gloss Granite "Warp Speed" (option); Brass Monkey "Devil's Rim" (option); Lightweight Low Gloss Black (standard on RE WB) | S4 |
| 2023 | Carbon Black (listed as "optional" on Hellcat and RE with the Widebody Package); Lightweight Low Gloss Black (standard on RE WB). "Warp Speed" Carbon Black is listed only for GT and R/T Scat Pack with the HEMI Orange Package | S5 |

**Offset:** ET −2.5 mm. This comes only from a forum thread and a replica-wheel listing (S20) and is unverified. Bolt pattern and centre bore were not verified.

### Brakes

These are from the SRT/Brembo High-performance Brake Package, standard on SRT Hellcat models.

| Item | 2018–2020 | 2021–2023 | Source |
|---|---|---|---|
| Front rotor | 15.4 × 1.34 in (390 × 34 mm), two-piece aluminum hat, vented and slotted | 15.7 × 1.34 in (400 × 34 mm), two-piece aluminum hat, directional-vane vented and slotted | S1, S2, S6; S3–S5 |
| Front caliper | Brembo six-piston fixed monoblock, aluminum; listed "caliper size" 1.42 in (36 mm) | same | S1–S6 |
| Front swept area | 424 sq in (2,735 cm²) | 442 sq in (2,852 cm²) | S1, S2, S6; S3–S5 |
| Rear rotor | 13.8 × 1.10 in (350 × 28 mm), vented and slotted | 13.8 × 1.10 in (350 × 28 mm), vented | S1, S2, S6; S3–S5 |
| Rear caliper | Brembo four-piston fixed, aluminum housing; listed size 1.26 in (32 mm) | same | S1–S6 |
| Rear swept area | 316 sq in (2,036 cm²) | same | S1–S6 |
| Booster | 8 + 9 in (203 + 209 mm) tandem-diaphragm vacuum | same | S1–S5 |

- The C&D test car (MY18 WB) is listed with "15.4-in vented, slotted discs/13.8-in vented, slotted discs" (S11).
- [DERIVED] The front share of total swept area is [57 %] (2018–20) and [58 %] (2021–23). This is not a brake-bias specification.

**Caliper colors:**
- The 2019 Hellcat option list shows "Brake Calipers – Black (XS9) – $495". Gunmetal Gray (XTM) and Orange (XTU) are listed at the same price (S19).
- Red as the no-cost standard color comes only from owner forums (S21, unverified). So does the report that the 2022–23 Jailbreak program added blue and yellow.
- The Dodge spec sheets do not state caliper color.
- The reference photos show orange-red calipers.

## 4. Engine

| Item | Value | Applies to | Source |
|---|---|---|---|
| Type | supercharged 6.2 L HEMI V8: 90° V, pushrod, 16 valves, cast-iron block, aluminum heads, port injection | WB and STD | S1–S5 |
| Displacement | 376 cu in (6,166 cm³) | | S1–S5 |
| Bore × stroke | 4.09 × 3.58 in (103.9 × 90.9 mm) | | S1–S5 |
| Compression ratio | 9.5 : 1 | | S1–S5 |
| Power (SAE net) | 717 bhp (535 kW) @ 6,000 rpm | 2019–2023 | S1–S5 |
| Torque (SAE net) | 656 lb-ft (889 N·m) @ 4,800 rpm | 2019–2023 | S1–S5 |
| Power and torque, MY18 | 707 bhp (527 kW) @ 6,000; 650 lb-ft (881 N·m) @ 4,800 | MY18 | S6. C&D's 2016 test lists 650 lb-ft @ 4,000 rpm (S13); the 2018 sheet says 4,800. |
| Max engine speed | 6,200 rpm | | S1–S6. S8 says "Higher rpm limit: 6,500 rpm versus 6,200 rpm" (Redeye vs Hellcat). S11 says "6200-rpm fuel cutoff". |
| Idle speed | not published | | – |
| Boost | 80 kPa (11.6 psi) maximum, electronic bypass valve | | S10: "regulate boost pressure to a maximum of 80 kPa (11.6 psi)". S8: "Increased boost pressure: 14.5 psi versus 11.6 psi" (Redeye vs Hellcat). |
| Supercharger | IHI twin-screw, 2,380 cm³/rev (2.4 L), drive ratio 2.36 : 1, maximum 14,600 rpm | | S10. S17 gives rotor speeds of 14,500 / 24,000 rpm. |
| Induction airflow | 1,048 CFM combined (dual-snorkel hood, Air Catcher headlamp, wheel-liner inlet) | 2019–2023 | S1–S5 |

### Full-throttle torque curve

No manufacturer curve or magazine engine-dyno table was found. These are the published anchors:

| rpm | Torque | Power | Basis | Source |
|---|---|---|---|---|
| 1,200 | 411 lb-ft (557 N·m) | [94 hp] | "delivers a mammoth 411 pound-feet (557 Nm) of twist from 1,200 rpm" (707-hp engine, 2014) | S16 |
| 4,800 | 656 lb-ft (889 N·m), peak | [600 hp] | rating | S1 |
| 6,000 | [627.6 lb-ft (851 N·m)] | 717 hp, peak | rating; torque = 717 × 5,252 / 6,000 | S1, DERIVED |
| 6,200 | – | – | fuel cut-off | S1, S11 |

Owner-forum chassis-dyno reports for stock 717-hp cars (S22, unverified) show:
- about 620–680 hp and 590–640 lb-ft at the wheels on Dynojet dynos;
- wheel torque peaking around 3,700–4,500 rpm;
- power peaking around 6,100–6,200 rpm.

[EST] Torque table for the simulation. The anchors above are fixed. The shape between them is an estimate guided by the forum dyno reports. For a MY18 car, scale torque by 650/656.

| rpm | lb-ft | N·m | hp |
|---|---|---|---|
| 1,000 | 370 | 502 | 70 |
| 1,200 | 411 | 557 | 94 |
| 1,500 | 445 | 603 | 127 |
| 2,000 | 500 | 678 | 190 |
| 2,500 | 540 | 732 | 257 |
| 3,000 | 585 | 793 | 334 |
| 3,500 | 620 | 841 | 413 |
| 4,000 | 643 | 872 | 490 |
| 4,500 | 654 | 887 | 560 |
| 4,800 | 656 | 889 | 600 |
| 5,000 | 655 | 888 | 624 |
| 5,500 | 645 | 875 | 675 |
| 6,000 | 628 | 851 | 717 |
| 6,200 | 605 | 820 | 714 |

## 5. Transmission and driveline

### TorqueFlite 8HP90 eight-speed automatic (optional on SRT Hellcat)

| Gear | Dodge sheets 2019–2023 (S1–S5) | Dodge 2015 release (S10) | ZF data sheet (S15) | Recommended |
|---|---|---|---|---|
| 1 | 4.71 | 4.71 | 4.714 | 4.714 |
| 2 | 3.14 | 3.14 | 3.143 | 3.143 |
| 3 | 2.10 | 2.10 | 2.106 | 2.106 |
| 4 | 1.67 | 1.67 | 1.667 | 1.667 |
| 5 | 1.29 | 1.29 | 1.285 | 1.285 |
| 6 | 1.00 | 1.00 | 1.000 | 1.000 |
| 7 | 0.84 | 0.84 | 0.839 | 0.839 |
| 8 | 0.67 | 0.67 | 0.667 | 0.667 |
| R | 3.32 | 3.30 | 3.317 | 3.317 |
| Ratio spread | – | "7.03 ratio spread" | 7.067 | |

ZF's sheet covers the 8HP 90 S/SX special-vehicle derivative. Its standard ratio set is the first-generation 8HP gearset, and Dodge's rounded figures match it.

Use the ZF values. Dodge's rounding is inconsistent: third gear is 2.10 for the 8HP90 but 2.11 for the 8HP70 in the same sheet, and reverse is 3.30 in one document and 3.32 in another.

| Item | Value | Source |
|---|---|---|
| Final drive, automatic | 2.62 : 1, "asymmetric limited-slip, performance-tuned (standard)" | S1–S5, S10 |
| Optional final drive | 3.09 : 1. The sheets list it as optional on the Redeye only, but the 2019 Hellcat option list shows "3.09 Rear Axle Ratio (DPM) – $1,095" (S19). This conflict is unresolved for non-Redeye cars. | S1–S5, S19 |
| Overall top gear, automatic | 1.76 in the sheets; [1.748] with 0.667 × 2.62 | S1–S5 |
| Shift time | "160 millisecond shifts in Track mode" | S10 |
| Torque converter | not published. The Redeye's converter has "an 18 percent increase in torque multiplication" over the standard Hellcat's. | S8 |

### Tremec TR-6060 six-speed manual (standard on SRT Hellcat)

| Item | Value | Source |
|---|---|---|
| Gear ratios 1–6 | 2.26 / 1.58 / 1.19 / 1.00 / 0.77 / 0.63 | S1–S6 |
| Reverse | 2.90 | S1–S6 |
| Final drive | 3.70 : 1 | S1–S6 |
| Overall top gear | 2.33 | S1–S6 |
| Clutch | ZF-Sachs 258 mm twin-disc | S1–S6 |

C&D confirms the first three: "With a 2.26:1 first, 1.58:1 second, and 1.19:1 third-gear ratio" (S11).

### Differential

- **Type:** "asymmetric limited-slip, performance-tuned" (S1–S6).
- **Behavior:** Dodge's 2015 Hellcat powertrain release (S10) says "An asymmetric limited-slip differential allows for unique bias-ratio tuning for on- and off-throttle behavior". It adds that under trail-braking the differential "further tightens".
- **Hardware:** 230 mm axle, aluminum housing, "Robust four-pinion differential" (S10).
- S10 describes the Charger SRT Hellcat; the Challenger is assumed identical.
- The mechanism type, preload and bias ratios are not published.

### [DERIVED] Road speed per gear

Assumes a 350.4 mm rolling radius and no slip.

| Gear | Auto (2.62): km/h per 1,000 rpm | Auto at 6,200 rpm | Manual (3.70): km/h per 1,000 rpm | Manual at 6,200 rpm |
|---|---|---|---|---|
| 1 | 10.70 | 66 km/h (41 mph) | 15.80 | 98 km/h (61 mph) |
| 2 | 16.04 | 99 km/h (62 mph) | 22.60 | 140 km/h (87 mph) |
| 3 | 23.94 | 148 km/h (92 mph) | 30.00 | 186 km/h (116 mph) |
| 4 | 30.25 | 188 km/h (117 mph) | 35.70 | 221 km/h (137 mph) |
| 5 | 39.24 | 243 km/h (151 mph) | 46.37 | 287 km/h (179 mph) |
| 6 | 50.42 | 313 km/h (194 mph) | 56.67 | drag-limited |
| 7 | 60.09 | drag-limited | – | – |
| 8 | 75.59 | drag-limited | – | – |

## 6. Performance

No instrumented test of a 717-hp (2019–2023) Hellcat Widebody was found. The closest tested cars are:
- the 707-hp MY18 Widebody: same body, tires and aero, and about 10 hp less;
- the 797-hp 2019 Redeye Widebody.

| Metric | Value | Car | Source | Type |
|---|---|---|---|---|
| 0–60 mph | 3.4 s ("3.4 in Widebody vs. 3.5 in standard Hellcat") | MY18 WB | S7 | OFFICIAL claim |
| | 3.8 s ("the Challenger Hellcat Widebody automatic hits 60 mph in 3.8 seconds") | MY18 WB automatic | S11 | TEST, stated in the article text; full data not published |
| | 4.0 s | MY18 WB manual | S11 | TEST |
| | 3.4 s; 0–100 mph 7.3 s | MY18 WB automatic | S14 | 2ND (Motor Trend 7/2018, quoted in a comment) |
| | 3.7 s in the test box (the article text says 3.6 s) | 2019 RE WB (797 hp) | S12 | TEST |
| | 3.6 s | 2016 STD automatic | S13 | TEST |
| 0–100 km/h | no test found. ≈ 3.9–4.0 s under C&D-style test conditions; ≈ 3.5 s under the conditions behind Dodge's claim | WB | – | EST. 100 km/h = 62.1 mph, so add 0.1–0.2 s to the 0–60 mph time. |
| Quarter mile | 10.9 s @ 127 mph [204 km/h] | 2019 WB (717 hp) | S8 | OFFICIAL claim |
| | 11.2 s @ 125 mph | 2019 STD | S8 | OFFICIAL claim |
| | 11.8 s @ 126 mph | MY18 WB automatic | S11 | TEST (article text) |
| | 12.4 s @ 120 mph | MY18 WB manual | S11 | TEST |
| | 11.5 s @ 122.2 mph | MY18 WB automatic | S14 | 2ND |
| | 11.8 s @ 125 mph | 2019 RE WB | S12 | TEST |
| Top speed | 195 mph [314 km/h] | WB, in both the 2018 release and the 2019 table | S7, S8 | OFFICIAL |
| | 199 mph [320 km/h] | STD | S8 | OFFICIAL |
| | 203 mph | RE and RE WB | S8 | OFFICIAL |
| | "Top speed (drag limited): 195 mph" | MY18 WB manual | S11 | listed by C&D |
| Braking, 70–0 mph | 154 ft [46.9 m], "with no fade" | MY18 WB manual, summer tires, 390 mm rotors | S11 | TEST |
| | 152 ft [46.3 m] | 2019 RE WB | S12 | TEST |
| | 159 ft [48.5 m] | 2016 STD automatic | S13 | TEST |
| Braking, 60–0 mph or 100–0 km/h | not found for WB. [≈ 37 m from 100 km/h], assuming the same constant deceleration as the 154-ft stop (1.06 g) | WB | – | DERIVED |
| Skidpad (300-ft) | 0.95 g | MY18 WB manual | S11 | TEST |
| | 0.95 g | 2019 RE WB | S12 | TEST |
| | 0.91 g (S11 text) / 0.92 g (S13) | STD | S11, S13 | TEST |
| | ".97 g in Widebody vs. .93 g in standard Hellcat" | WB | S7 | OFFICIAL claim |
| Figure-eight | 24.8 s @ 0.88 g average | MY18 WB automatic | S14 | 2ND |
| "Lateral acceleration" | 1.11 g | MY18 WB automatic | S14 | 2ND. It contradicts all other data; do not use. |
| Lap time | about 2 s per lap faster than STD on a 1.7-mile road course | WB | S7 | OFFICIAL claim |

**Recommended acceptance targets for the sandbox:**
- 0–60 mph: 3.8 s ± 0.2 s. This is the tested time on a street surface; Dodge's 3.4 s needs a prepared surface.
- Quarter mile: 11.8 s.
- 70–0 mph: 46.9 m.
- Skidpad: 0.95 g.
- Top speed: 195 mph, drag-limited (see section 8).

## 7. Chassis

| Item | Value | Source |
|---|---|---|
| Front suspension, layout | independent short- and long-arm (SLA) with a high upper A-arm and lateral and diagonal lower links | S1–S6 |
| Front suspension, 2018–2019 | "coil spring over gas-charged ADS Bilstein shock absorbers and 34 mm solid stabilizer bar" (SRT Hellcat models) | S1, S6 |
| Front suspension, 2020–2023 | same layout; the stabilizer bar is "34 mm for R/T Scat Pack Widebody and SRT models", hollow | S2–S5 |
| Rear suspension, layout | five-link independent with coil springs and an isolated suspension cradle | S1–S6 |
| Rear suspension, 2018–2019 | "link-type 22 mm solid stabilizer bar, gas-charged ADS Bilstein shock absorbers and isolated suspension cradle" | S1, S6 |
| Rear suspension, 2020–2023 | "Link-type 19 mm (22 mm on Widebody models) hollow stabilizer bar" | S2–S5 |
| Dampers | SRT-tuned three-mode Bilstein Adaptive Damping Suspension: Auto/Street, Sport, Track | S1–S5, S8 |
| Anti-roll bars | front 34 mm, rear 22 mm (WB). The 2018–19 sheets say solid and the 2020–23 sheets say hollow; the diameters agree. | S1–S6 |
| Spring rates, damper curves, ride height per corner, CG height, roll centers | not published | – |
| Steering type | Electric power steering with multi-mode assist, standard on the Hellcat Widebody from launch. S7: "a new standard electric power steering (EPS) system – a first for Hellcat". The MY18 STD Hellcat kept hydraulic assist (S6). All 2019+ Hellcats have EPS (S8). | S6–S8 |
| Steering ratio | 14.4 : 1 ("all RWD models"). C&D: "the 14.4:1 steering ratio is quick". | S1–S6, S11 |
| Turns lock to lock | 2.52 (2018–19 sheets), 2.5 (2020–23 sheets), "SRT Hellcat models" | S1–S6 |
| Turning circle, curb to curb | 38.7 ft [11.80 m], "SRT Hellcat models and Widebody models". MY18 STD Hellcat: 38.5 ft. | S1–S6 |
| Mean road-wheel angle at lock | [≈ 31°] = 2.5 × 360° / 14.4 | DERIVED |
| Outer / inner wheel angle at lock | [≈ 31° outer; 36–42° inner, depending on the Ackermann percentage], from the turning circle, wheelbase and track | DERIVED, approximate |

C&D classifies the suspension as "multilink/multilink" (S11).

## 8. Aerodynamics

| Item | WB | STD Hellcat | Source |
|---|---|---|---|
| Drag coefficient Cd | 0.398 (all years 2018–2023) | 0.382 (2019–2023); 0.383 (2018) | S1–S6 |
| Frontal area | 26.8 sq ft, listed as 2.5 m² [2.49 m²] | 26.0 sq ft, listed as 2.4 m² [2.42 m²] | S2–S5 (not in the 2018 and 2019 sheets) |
| CdA | [0.99 m²] | [0.92 m²] | DERIVED |
| Lift / downforce | not published | not published | – |

For reference, other Challengers: Cd 0.337 (SXT) and 0.365 (GT, R/T, R/T Scat Pack) (S2–S5).

**[DERIVED] Consistency check at Dodge's 195 mph** (87.2 m/s, air density 1.204 kg/m³):
- Aerodynamic drag power ≈ 0.5 × 1.204 × 0.99 × 87.2³ ≈ 395 kW.
- Rolling resistance ≈ 22 kW, assuming Crr 0.012 and 2,105 kg including the driver.
- Total ≈ 417 kW needed at the wheels.
- In 7th gear the engine turns ≈ 5,220 rpm and makes ≈ 482 kW on the estimated curve. At 85–88 % driveline efficiency that is 410–425 kW at the wheels.

So Cd, frontal area, gearing and the torque estimate all agree with a drag-limited 195 mph. Sixth gear runs out at ≈ 194 mph at 6,200 rpm.

## 9. Driver's view

These interior dimensions apply to all Challengers and are not trim-specific (S1–S5; knee clearance appears only in S2–S5):

| Item | in | mm |
|---|---|---|
| Front headroom | 39.3 | 999 |
| Front legroom | 42.0 | 1,067 |
| Front shoulder room | 58.5 | 1,485 |
| Front hip room | 55.3 | 1,404 |
| Front knee clearance | 4.4 | 112 |
| Driver seat travel | 10.0 | 255 |
| Driver seat-back recline range | 64° | – |

Nothing found anywhere publishes the seating reference point (SgRP, H-point) height, the seat height, the eye point or hood/cowl sight-line angles.

**[EST] Eye-height estimate**
1. Assume the published front headroom is SAE J1100 "effective head room" (H61). H61 is the distance from the SgRP to the headliner along a line 8° rearward of vertical, plus 102 mm. That gives an SgRP-to-headliner distance of ≈ 999 − 102 = 897 mm, of which ≈ 888 mm is vertical.
2. Headliner height ≈ overall height 1,460 mm minus 30–75 mm for roof skin, bows and headliner. That is ≈ 1,385–1,430 mm above the ground at curb weight.
3. SgRP ≈ 0.50–0.54 m above the ground.
4. The SAE J941 eyellipse centroid sits ≈ 638 mm above the SgRP. That gives an eye height of ≈ 1.14–1.18 m.

**Use 1.16 m ± 0.05 m.** This is higher than the project brief's 1.05–1.10 m. Before fixing the cockpit camera, check it in Blender against `reference/Interior 2.jpg`, using the visible hood scoop and cowl line. The driver's weight lowers the car by a few millimetres.

## 10. Not found or not verified

1. Front and rear overhang separately. Only the 2,067 mm total is derived.
2. Approach, departure and breakover angles.
3. Mirror-to-mirror width specific to the Widebody. The 2,169 mm value has no trim qualifier.
4. A MotorTrend-measured weight distribution. Only C&D's 56.7 % front (MY18 WB manual) exists.
5. CG height, spring rates, damper curves and roll centers.
6. Wheel offset ET −2.5 mm (forum and replica listings only), bolt pattern and centre bore.
7. Red as the standard caliper color, and the 2022–23 Jailbreak blue and yellow options (forums only).
8. Idle speed.
9. The full-throttle torque curve. Only three published anchors exist; the section 4 table is an estimate, and the forum dyno figures are unverified.
10. Any instrumented test of a 717-hp Hellcat Widebody. All tests found are of the MY18 707-hp Widebody or the 2019 797-hp Redeye Widebody.
11. A measured 0–100 km/h time, and 60–0 mph braking, for the Widebody.
12. The MotorTrend 7/2018 Widebody figures, seen only via a FastestLaps user comment. The "1.11 g lateral" figure in particular is doubtful.
13. Limited-slip mechanism type, preload and bias ratios, and torque-converter characteristics.
14. Whether the 3.09 axle could be ordered on non-Redeye 2019 Hellcats. MoparInsiders says yes; the Dodge sheets say no.
15. Maximum road-wheel steering angles (derived only).
16. Lift coefficients and downforce.
17. H-point (SgRP) height and eye height (estimate only).
18. The reference car's model year. Its hood points to MY2018 rather than 2019–2023 (see the flag at the top).

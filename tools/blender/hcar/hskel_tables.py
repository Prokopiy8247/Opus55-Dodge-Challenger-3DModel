"""Hellcat physics skeleton tables (pure Python): masses, stations, structural coordinates, panel
resolutions. Car frame as for the visual model (x right, y forward, z up, y = 0 mid-wheelbase).

Mass target: MY18 Challenger SRT Hellcat Widebody automatic, 2,040 kg curb, 57 / 43 % front / rear
(docs/specs.md section 2; Car and Driver measured 56.7 %). Centre of mass target y = 1.4755 - 0.43 * 2.951
= 0.207 m.
"""

MASS_TOTAL = 2040.0
FRONT_SHARE = 0.57
WHEELBASE = 2.951
COM_Y_TARGET = 1.4755 - (1.0 - FRONT_SHARE) * WHEELBASE      # 0.2066 m

# --------------------------------------------------------------------------------------------
# fixed masses (kg) of the named groups; the body cell takes the rest (see hskel.distribute_mass)
GROUP_MASS = {
    "engine": 270.0, "transmission": 95.0, "driveshaft": 15.0, "differential": 44.0, "subframe_rear": 32.0,
    "exhaust": 30.0, "fuel_tank": 60.0, "battery": 22.0, "radiator": 34.0,   # radiator: cooling package
    "seat_FL": 25.0, "seat_FR": 25.0, "seat_rear": 20.0, "dash": 22.0, "column": 8.0,
    "hood": 22.0, "trunk": 16.0, "door_FL": 30.0, "door_FR": 30.0, "fender_L": 12.0, "fender_R": 12.0,
    "bumper_F": 10.0, "bumper_R": 10.0, "mirror_L": 1.6, "mirror_R": 1.6, "headlight_L": 3.0, "headlight_R": 3.0,
    "glass_windshield": 15.0, "glass_rear": 10.0, "glass_side_FL": 5.0, "glass_side_FR": 5.0,
    "glass_quarter_L": 2.0, "glass_quarter_R": 2.0, "spoiler": 3.0,
    # per corner: hub, knuckle, caliper, outer arm mass; the rear knuckle's lower-rear node (spring, damper, anti-roll
    # bar link) is weighted 1.75 so the stiffer dampers of D-036 keep S below 2.5 (3 kg moved from the rear rim)
    "knuckle_front": 28.0, "knuckle_rear": 23.0,
    "rim_front": 25.0, "rim_rear": 19.0, "tire": 18.0,   # per wheel; the rim rings carry the rim and the brake disc
    "susp_front_arms": 10.0, "susp_rear_links": 8.0,  # per side, arm / link inner pivots
    "rack": 12.0,                                    # rack + front anti-roll bar
}

# --------------------------------------------------------------------------------------------
# tire and wheel (305/35 ZR20 on 20 x 11 in)
TIRE_SECTIONS = 24
TIRE_R_OUT = 0.3608           # unloaded outer radius (visual tire)
RIM_R = 0.254                 # bead seat radius (20 in)
RIM_HALF_W = 0.135            # bead seats at +-0.135 m from the wheel centre plane
TREAD_HALF_W = 0.140          # tread shoulders
TIRE_PRESSURE_PA = 241000.0   # 35 psi gauge
AXLE_IN, AXLE_OUT = 0.110, 0.060   # axle nodes inboard / outboard of the wheel centre plane

# --------------------------------------------------------------------------------------------
# body structure (right side; the left side is mirrored). Cabin stations along y.
CABIN_Y = [0.92, 0.66, 0.40, 0.14, -0.12, -0.36, -0.58, -0.84, -1.06]
RAIL_Y = [0.80, 0.62, 0.45, 0.29, 0.14, -0.12, -0.36, -0.60, -0.84, -1.06, -1.24, -1.42, -1.60]   # pillar line
SILL = {"x_out": 0.865, "x_in": 0.790, "z_lo": 0.215, "z_hi": 0.315}
FLOOR_X = 0.42
FRONT_RAIL_Y = [0.98, 1.20, 1.45, 1.70, 1.92, 2.08]
FRONT_RAIL = {"x_in": 0.370, "x_out": 0.470, "z_lo": 0.265, "z_hi": 0.385}
CRUSH_CAN_Y = 2.170
BUMPER_F = {"y": 2.265, "depth": 0.060, "z": 0.470, "x": [0.0, 0.24, 0.42, 0.62, 0.76]}
CORE = {"y": 2.075, "z_lo": 0.330, "z_hi": 0.800, "x": [0.0, 0.34, 0.66]}
APRON = [(0.800, 0.990, 0.880), (0.755, 1.230, 0.865), (0.720, 1.475, 0.850), (0.705, 1.720, 0.830), (0.680, 1.960, 0.810)]
APRON_LO = [(0.640, 1.100, 0.640), (0.585, 1.475, 0.780), (0.640, 1.850, 0.640)]   # wheel house inner top, strut top
REAR_RAIL_Y = [-1.06, -1.30, -1.55, -1.80, -2.05, -2.28, -2.44]
REAR_RAIL = {"x_in": 0.400, "x_out": 0.500, "z_lo": [0.420, 0.420, 0.420, 0.420, 0.370, 0.370, 0.400],
             "z_hi": [0.530, 0.530, 0.530, 0.530, 0.480, 0.480, 0.510]}
BUMPER_R = {"y": -2.505, "depth": 0.060, "z": 0.480, "x": [0.0, 0.24, 0.45, 0.66, 0.78]}
REAR_PANEL = {"y": -2.465, "z_lo": 0.650, "z_hi": 0.990, "x": [0.0, 0.30, 0.60]}
WHEELHOUSE_R = [(0.610, -1.075, 0.430), (0.610, -1.180, 0.700), (0.610, -1.475, 0.815), (0.610, -1.770, 0.700),
                (0.610, -1.880, 0.430)]
REAR_TOWER = (0.560, -1.565, 0.760)
SHELF_Y, SHELF_Z = -1.50, 1.085
B_PILLAR_Y = -0.580            # latch post just behind the door's rear shut line (y -0.538)
B_PILLAR = [(0.840, 0.315), (0.860, 0.620), (0.845, 0.960)]             # (x, z) below the roof rail
C_PILLAR_Y = -1.060
C_PILLAR = [(0.865, 0.315), (0.880, 0.640), (0.840, 0.990)]
A_HINGE = [(0.820, 0.800, 0.315), (0.845, 0.800, 0.600), (0.830, 0.800, 0.900)]   # hinge pillar at the door front (y 0.73)
COWL = {"y": 0.900, "z": 0.975, "x": [0.0, 0.38, 0.76]}
FIREWALL = {"y": 0.975, "z": [0.560, 0.820], "x": [0.0, 0.38]}
DASH_BAR = {"y": 0.640, "z": 0.780, "x": [0.0, 0.375, 0.74]}

# --------------------------------------------------------------------------------------------
# panels: sampling of the visual panel grids (columns, rows) - node spacing ~11-16 cm
# (columns, rows); for the centre panels the columns count the right half including the centreline
PANEL_RES = {
    "door": (11, 6), "door_inner": (6, 4), "fender": (10, 6), "quarter": (12, 7), "roof": (5, 9),
    "hood": (5, 8), "hood_inner": (3, 4), "trunk": (4, 6), "trunk_inner": (3, 3), "fascia": (6, 5),
    "bumper_r": (6, 5), "windshield": (5, 6), "rear_glass": (5, 5), "door_glass": (7, 3), "quarter_glass": (3, 3),
}
PANEL_NODE_MIN_MASS = 0.25        # kg: lighter panel nodes would need softer beams than useful

# cell node mass weights x (attached stiffness / median) ** CELL_STIFFNESS_EXP (D-031)
CELL_STIFFNESS_EXP = 0.0

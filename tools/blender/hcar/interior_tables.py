"""Interior layout tables (pure Python, no bpy): driver package, instrument mapping, part positions.

Car frame as for the exterior (docs/model_notes.md): metres, Z up, +Y forward, +X right, y = 0 halfway
between the axles, z = 0 on the ground. Left-hand drive: the driver sits at x < 0.

The driver package follows the published Challenger interior figures (front headroom 999 mm, shoulder
room 1,485 mm, hip room 1,404 mm; docs/specs.md section 9) and its SAE J1100/J941 eye-height estimate
(1.16 +- 0.05 m; the brief says 1.05-1.10 m): H-point 0.49 m above the ground (0.27 m above the floor),
torso angle 25 deg, eye at 1.12 m (decision D-020).
"""
import math

SEAT_X = 0.375                       # front seat centrelines at x = -+SEAT_X
H_POINT = (-SEAT_X, -0.11, 0.490)    # driver hip point
TORSO_DEG = 25.0                     # seat back angle from vertical
EYE = (-SEAT_X, -0.36, 1.120)        # driver's eye point (cockpit camera)
FOV_H_DEG = 85.0                     # cockpit camera horizontal field of view (configurable in Unity)

# steering: column axis from the wheel centre towards the dash, 23 deg above horizontal going forward-down
WHEEL_CENTRE = (-SEAT_X, 0.250, 0.860)
COLUMN_DEG = 23.0                    # wheel plane tilt from vertical (= column angle from horizontal)
WHEEL_R = 0.180                      # rim centreline radius (370 mm outer diameter)
WHEEL_FLAT = 0.148                   # flat bottom: rim centreline chord at -WHEEL_FLAT below the centre
STEER_LOCK_TO_LOCK_TURNS = 2.6       # steering wheel turns lock to lock (brief: 2.5-3)

# instrument cluster (pods face the eye)
CLUSTER_CENTRE = (-SEAT_X, 0.54, 0.928)
POD_DX = 0.110                       # pod centres at cluster x -+ POD_DX (tach left, speedo right; photo fit)
POD_R = 0.060                        # dial radius
POD_BEZEL_R = 0.070
DISPLAY_W, DISPLAY_H = 0.086, 0.092  # centre TFT: the window between the two pod bezels

# gauge mapping (angles clockwise from 12 o'clock, degrees), shared with the Unity gauge component
GAUGES = {
    "tach": {"min": 0.0, "max": 7000.0, "a_min": -120.0, "a_max": 120.0, "redline": 6000.0, "unit": "rpm"},
    "speedo": {"min": 0.0, "max": 200.0, "a_min": -120.0, "a_max": 120.0, "unit": "mph"},
}


def gauge_angle(name, value):
    g = GAUGES[name]
    t = (min(max(value, g["min"]), g["max"]) - g["min"]) / (g["max"] - g["min"])
    return g["a_min"] + t * (g["a_max"] - g["a_min"])


# centre stack (8.4 in touchscreen with a vent on each side, carbon surround)
STACK_CENTRE = (0.0, 0.585, 0.860)
STACK_TILT_DEG = 14.0                # face tilted back from vertical
SCREEN_W, SCREEN_H = 0.186, 0.112    # 8.4 in, 16:9.6
START_BUTTON = (-0.200, 0.582, 0.700)      # dash face below the stack's left vent (photo fit, cabin2)
START_BUTTON_TILT_DEG = 8.0                # dash face tilt from vertical there

# pedals (driver): pivot under the dash, pads on arms; rotation about the car's x axis
PEDAL_PIVOT_YZ = (0.865, 0.665)
PEDALS = {
    "accelerator": {"x": -0.285, "pad_yz": (0.770, 0.335), "pad_w": 0.060, "pad_h": 0.170, "travel_deg": 16.0},
    "brake": {"x": -0.430, "pad_yz": (0.715, 0.405), "pad_w": 0.135, "pad_h": 0.075, "travel_deg": 20.0},
}
FOOTREST = {"x": -0.620, "yz": (0.866, 0.332)}   # on the 50 deg toe board, 18 mm proud of the carpet

# seats
FRONT_SEAT = {"half_w": 0.255, "bolster_h": 0.060, "back_len": 0.80, "back_t": 0.10}
REAR_SEAT_X = 0.370                      # outer rear seats (the wheel houses come in to |x| = 0.598)
REAR_HW_FRONT, REAR_HW_BACK = 0.665, 0.575 # bench half width ahead of / beside the wheel houses
REAR_CUSHION_FRONT = (-0.705, 0.585)     # (y, z) of the cushion's front top edge
REAR_BACK_BOTTOM = (-1.150, 0.520)
REAR_BACK_TOP = (-1.395, 1.075)

# console (front seats are 0.51 m wide: 1 cm clearance to the console on each side)
CONSOLE_W = 0.205
# console top: flat at 0.585 m, rising as a 35 deg "waterfall" to the stack (switch bank on it);
# positions from back-projecting reference/Interior 2.jpg through the fitted camera (tools/ref/backproject.py)
CONSOLE_TOP = ((-0.585, 0.585), (0.05, 0.580), (0.34, 0.592), (0.545, 0.738))   # (y, z)
SWITCH_BANK_Y = 0.417                            # centre of the switch bank on the waterfall
SHIFTER = (0.0, 0.300, 0.585)                    # base of the selector lever
CUPHOLDERS = ((0.018, 0.060), (0.018, -0.040))   # (x, y) centres, tandem
ARMREST = {"y0": -0.115, "y1": -0.560, "z": 0.665, "w": 0.205}

# interior mirror and sun visors
MIRROR = (0.0, 0.300, 1.305)
VISOR_Y = (0.095, 0.270)


def column_axis():
    """Unit vector along the column from the wheel towards the dash (forward and down)."""
    a = math.radians(COLUMN_DEG)
    return (0.0, math.cos(a), -math.sin(a))


def wheel_up():
    """Unit vector in the wheel plane pointing to 12 o'clock (up and slightly forward)."""
    a = math.radians(COLUMN_DEG)
    return (0.0, math.sin(a), math.cos(a))

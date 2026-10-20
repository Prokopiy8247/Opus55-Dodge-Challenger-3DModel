"""P6: the energy ledger counts the work the gearbox output does on the axle side of the driveline (driveWork), so the
"no energy created" check also holds while the engine drives after a contact (S5 up the ramp, S7 through the debris).
Telemetry only: the dynamics are unchanged."""
import io
from pathlib import Path

A = Path(r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets")


def patch(rel, pairs):
    p = A / rel
    raw = io.open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    s = raw.replace("\r\n", "\n")
    for a, b in pairs:
        if s.count(a) != 1:
            raise SystemExit(f"{rel}: {s.count(a)} x {a[:70]!r}")
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
    print("patched", rel)


patch("Sim/Vehicle/VehicleTypes.cs", [(
    "        public double aeroWork;    // J, work of the aerodynamic forces (negative: drag)\n",
    "        public double aeroWork;    // J, work of the aerodynamic forces (negative: drag)\n"
    "        public double driveWork;   // J, work of the gearbox output on the axle side (the engine's input to the ledger)\n")])

patch("Sim/Vehicle/VehicleControlJob.cs", [
    ("            float tcl = 0f, wcNew = st.carrierOmega, weNew = we;\n",
     "            float tcl = 0f, wcNew = st.carrierOmega, weNew = we;\n"
     "            float tCarrier = 0f;   // gearbox output torque on the carrier (energy ledger)\n"),
    ("                if (math.abs(tcl) <= cap)\n                {\n                    wcNew = st.carrierOmega + ac * dt;\n",
     "                if (math.abs(tcl) <= cap)\n                {\n                    tCarrier = g * eta * tin;\n                    wcNew = st.carrierOmega + ac * dt;\n"),
    ("                weNew = we + ae * dt;\n                wcNew = st.carrierOmega + ac * dt;\n",
     "                tCarrier = g * eta * tin;\n                weNew = we + ae * dt;\n                wcNew = st.carrierOmega + ac * dt;\n"),
    ("            st.engineOmega = math.max(weNew, 0f);\n            st.carrierOmega = wcNew;\n",
     "            st.engineOmega = math.max(weNew, 0f);\n"
     "            st.driveWork += (double)tCarrier * 0.5 * (st.carrierOmega + wcNew) * dt;\n"
     "            st.carrierOmega = wcNew;\n"),
])

patch("Sim/Core/SoftBodyWorld.cs", [
    ("            public double aeroWork;    // J, work of the aerodynamic forces since spawn (negative: drag)\n",
     "            public double aeroWork;    // J, work of the aerodynamic forces since spawn (negative: drag)\n"
     "            public double driveWork;   // J, work of the gearbox output on the driveline's axle side since spawn\n"),
    ("                r.aeroWork = st.aeroWork;\n", "                r.aeroWork = st.aeroWork;\n                r.driveWork = st.driveWork;\n"),
])

"""P6: the scenario's energy balance subtracts the drive and aero work and, for the debris run, adds the props' ledgers;
the time series gets the drive and aero work columns."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
rep = [
    ("            var m = w.Metrics(runner.VehicleBody, true);\n            double balance = m.Mechanical + m.Dissipated;\n",
     "            var m = w.Metrics(runner.VehicleBody, true);\n"
     "            // kinetic + stored + dissipated, less what the engine and the air put in or took out (the debris' own ledgers\n"
     "            // included: the car hands them energy): must not rise after the contact\n"
     "            double balance = m.Mechanical + m.Dissipated - m.driveWork - m.aeroWork + PropsEnergy();\n"),
    ('            Put("contact_and_friction_loss_J", F(balanceAtContact - (m.Mechanical + m.Dissipated), "F1"));\n',
     '            Put("contact_and_friction_loss_J", F(balanceAtContact - (m.Mechanical + m.Dissipated - m.driveWork - m.aeroWork + PropsEnergy()), "F1"));\n'
     '            Put("drive_work_after_contact_J", F(m.driveWork - driveAtContact, "F1"));\n'),
    ("            if (contactSimTime >= 0 && double.IsNaN(balanceAtContact))\n                balanceAtContact = balance;\n",
     "            if (contactSimTime >= 0 && double.IsNaN(balanceAtContact))\n            {\n                balanceAtContact = balance;\n"
     "                driveAtContact = m.driveWork;\n            }\n"),
    ("        double balanceAtContact = double.NaN, energyCreated;\n",
     "        double balanceAtContact = double.NaN, energyCreated, driveAtContact;\n"),
    ('                     "throttle,brake,steer,gap_m,cabin_vf_mps,cabin_accel_g,max_deformation_m,props_moved");\n',
     '                     "throttle,brake,steer,gap_m,cabin_vf_mps,cabin_accel_g,max_deformation_m,props_moved,drive_work_J,aero_work_J");\n'),
    ("                deform.ToString(\"F4\", Ic), propsMoved.ToString(Ic),\n",
     "                deform.ToString(\"F4\", Ic), propsMoved.ToString(Ic), m.driveWork.ToString(\"F1\", Ic), m.aeroWork.ToString(\"F1\", Ic),\n"),
    ("        int StopsReleased()\n",
     "        /// <summary>Debris run: the props' kinetic, stored and dissipated energy (zero otherwise).</summary>\n"
     "        double PropsEnergy()\n        {\n            if (spec.kind != Kind.Debris || props == null) return 0.0;\n"
     "            var w = runner.World;\n            double e = 0.0;\n            foreach (int bi in props.Bodies)\n            {\n"
     "                var pm = w.Metrics(bi, true);\n                e += pm.Mechanical + pm.Dissipated;\n            }\n            return e;\n        }\n\n"
     "        int StopsReleased()\n"),
]
for a, b in rep:
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")

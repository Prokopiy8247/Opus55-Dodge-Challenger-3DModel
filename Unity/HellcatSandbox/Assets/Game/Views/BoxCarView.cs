using System.Collections.Generic;
using Hellcat.Game.Core;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// Vertical-slice visuals: a box body whose corners are the 12 body nodes (b{station}{L|R}{lo|hi})
    /// and one cylinder per wheel placed on the rim centroid and spun with the rim nodes.
    /// </summary>
    public class BoxCarView : MonoBehaviour
    {
        public SimRunner runner;
        public Material bodyMaterial, wheelMaterial;
        public float wheelWidth = 0.24f;

        Mesh bodyMesh;
        int[,,] bodyNode;           // station, side (0 L, 1 R), height (0 lo, 1 hi) -> world node index
        int stations;
        Vector3[] bodyVerts;
        readonly List<int[]> faceCorners = new List<int[]>();
        readonly List<Transform> wheelObjects = new List<Transform>();

        void Start()
        {
            var w = runner.World;
            var def = runner.VehicleDefinition;
            int start = w.bodies[runner.VehicleBody].nodeStart;
            var names = new Dictionary<string, int>();
            for (int i = 0; i < def.nodes.Length; i++)
                names[def.nodes[i].name] = start + i;
            stations = 0;
            while (names.ContainsKey($"b{stations}Llo"))
                stations++;
            bodyNode = new int[stations, 2, 2];
            for (int s = 0; s < stations; s++)
                for (int side = 0; side < 2; side++)
                    for (int h = 0; h < 2; h++)
                        bodyNode[s, side, h] = names[$"b{s}{(side == 0 ? "L" : "R")}{(h == 0 ? "lo" : "hi")}"];

            // Quads (corner node triples per vertex), listed counter-clockwise seen from outside in the sim frame.
            for (int s = 0; s < stations - 1; s++)
            {
                AddQuad(N(s, 0, 0), N(s + 1, 0, 0), N(s + 1, 0, 1), N(s, 0, 1)); // left side
                AddQuad(N(s, 1, 0), N(s, 1, 1), N(s + 1, 1, 1), N(s + 1, 1, 0)); // right side
                AddQuad(N(s, 0, 1), N(s + 1, 0, 1), N(s + 1, 1, 1), N(s, 1, 1)); // top
                AddQuad(N(s, 0, 0), N(s, 1, 0), N(s + 1, 1, 0), N(s + 1, 0, 0)); // bottom
            }
            AddQuad(N(0, 0, 0), N(0, 0, 1), N(0, 1, 1), N(0, 1, 0)); // front (station 0 is the front)
            int last = stations - 1;
            AddQuad(N(last, 0, 0), N(last, 1, 0), N(last, 1, 1), N(last, 0, 1)); // rear

            bodyVerts = new Vector3[faceCorners.Count * 4];
            var tris = new List<int>();
            for (int f = 0; f < faceCorners.Count; f++)
            {
                int v = f * 4;
                tris.AddRange(new[] { v, v + 2, v + 1, v, v + 3, v + 2 });
            }
            bodyMesh = new Mesh { name = "BoxCarBody" };
            bodyMesh.MarkDynamic();
            UpdateBodyVerts();
            bodyMesh.SetTriangles(tris, 0);
            bodyMesh.RecalculateNormals();
            var body = new GameObject("Body");
            body.transform.SetParent(transform, false);
            body.AddComponent<MeshFilter>().sharedMesh = bodyMesh;
            body.AddComponent<MeshRenderer>().sharedMaterial = bodyMaterial;

            for (int k = 0; k < def.wheels.Length; k++)
            {
                var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Destroy(go.GetComponent<Collider>());
                go.name = "Wheel_" + def.wheels[k].name;
                go.transform.SetParent(transform, false);
                go.GetComponent<MeshRenderer>().sharedMaterial = wheelMaterial;
                wheelObjects.Add(go.transform);
            }
            runner.Stepped += _ => Refresh();
            Refresh();
        }

        int[] N(int s, int side, int h) => new[] { s, side, h };

        void AddQuad(params int[][] corners)
        {
            var list = new int[4];
            for (int i = 0; i < 4; i++)
                list[i] = bodyNode[corners[i][0], corners[i][1], corners[i][2]];
            faceCorners.Add(list);
        }

        void UpdateBodyVerts()
        {
            var pos = runner.World.pos;
            for (int f = 0; f < faceCorners.Count; f++)
                for (int k = 0; k < 4; k++)
                    bodyVerts[f * 4 + k] = pos[faceCorners[f][k]];
            bodyMesh.vertices = bodyVerts;
        }

        void Refresh()
        {
            UpdateBodyVerts();
            bodyMesh.RecalculateNormals();
            bodyMesh.RecalculateBounds();
            var w = runner.World;
            var def = runner.VehicleDefinition;
            int start = w.bodies[runner.VehicleBody].nodeStart;
            for (int k = 0; k < def.wheels.Length; k++)
            {
                var wd = def.wheels[k];
                float3 c = float3.zero;
                foreach (int n in wd.rim)
                    c += w.pos[start + n];
                c /= wd.rim.Length;
                float3 axis = math.normalizesafe(w.pos[start + wd.axleOuter] - w.pos[start + wd.axleInner]);
                float3 spoke = math.normalizesafe(w.pos[start + wd.rim[0]] - c);
                var t = wheelObjects[k];
                t.position = c;
                // Cylinder primitive: axis = local Y. Keep local Z on spoke 0 so the wheel visibly spins.
                t.rotation = Quaternion.LookRotation(math.normalizesafe(spoke - math.dot(spoke, axis) * axis), axis);
                t.localScale = new Vector3(2f * wd.radius, 0.5f * wheelWidth, 2f * wd.radius);
            }
        }
    }
}

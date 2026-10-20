"""Debug collection for a physics skeleton: PH_Nodes, PH_Beams_<category>, PH_Tris.

Edges render as tubes and nodes as small spheres through Geometry Nodes modifiers, so the
skeleton shows up in Eevee renders (node-beam overlay shots for the video), not only in the viewport.
"""
import bpy

from . import blend_util as bu

CATEGORY_COLORS = {
    "rigid": (0.55, 0.57, 0.60),
    "crush": (1.00, 0.45, 0.05),
    "panel": (0.95, 0.80, 0.20),
    "glass": (0.40, 0.80, 1.00),
    "plastic": (0.85, 0.30, 0.85),
    "tire": (0.08, 0.08, 0.08),
    "rim": (0.30, 0.30, 0.32),
    "suspension": (0.10, 0.85, 0.35),
    "hydro": (0.00, 0.90, 0.90),
    "mount": (0.90, 0.15, 0.15),
    "other": (0.70, 0.70, 0.70),
}


def _new_group(name):
    """GN group with Geometry in/out; (group, True) when it was just created, (group, False) when cached."""
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng, False
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    return ng, True


def _finish(ng, gout, geo_socket, material):
    """Geometry generated inside a node tree carries no material of its own: one group per material
    (named after it) sets it on the output."""
    setm = ng.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = material
    ng.links.new(geo_socket, setm.inputs["Geometry"])
    ng.links.new(setm.outputs["Geometry"], gout.inputs[0])


def _tube_group(radius, material):
    ng, fresh = _new_group(f"HC_BeamTubes_{material.name}_{round(radius * 1e4)}")
    if not fresh:
        return ng
    n = ng.nodes
    gin = n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    m2c = n.new("GeometryNodeMeshToCurve")
    circle = n.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = 6
    circle.inputs["Radius"].default_value = radius
    c2m = n.new("GeometryNodeCurveToMesh")
    ng.links.new(gin.outputs[0], m2c.inputs["Mesh"])
    ng.links.new(m2c.outputs["Curve"], c2m.inputs["Curve"])
    ng.links.new(circle.outputs["Curve"], c2m.inputs["Profile Curve"])
    _finish(ng, gout, c2m.outputs["Mesh"], material)
    return ng


def _sphere_group(radius, material):
    ng, fresh = _new_group(f"HC_NodeSpheres_{material.name}_{round(radius * 1e4)}")
    if not fresh:
        return ng
    n = ng.nodes
    gin = n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    m2p = n.new("GeometryNodeMeshToPoints")
    ico = n.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = radius
    ico.inputs["Subdivisions"].default_value = 1
    inst = n.new("GeometryNodeInstanceOnPoints")
    real = n.new("GeometryNodeRealizeInstances")
    ng.links.new(gin.outputs[0], m2p.inputs["Mesh"])
    ng.links.new(m2p.outputs["Points"], inst.inputs["Points"])
    ng.links.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    ng.links.new(inst.outputs["Instances"], real.inputs["Geometry"])
    _finish(ng, gout, real.outputs["Geometry"], material)
    return ng


def _add_gn(obj, group, material):
    mod = obj.modifiers.new("HC_Render", "NODES")
    mod.node_group = group
    obj.data.materials.append(material)
    return mod


def build(sk, collection_name, category_of, tube_radius=0.006, node_radius=0.015, parent=None):
    """category_of(material_name) -> key of CATEGORY_COLORS."""
    col = bu.collection(collection_name, parent)
    for obj in list(col.objects):
        bu.remove_object(obj.name)
    verts = [n["p"] for n in sk.nodes]

    nodes_obj = bu.mesh_object("PH_Nodes", verts, col=col)
    me = nodes_obj.data
    attr = me.attributes.new("mass", "FLOAT", "POINT")
    attr.data.foreach_set("value", [n["m"] for n in sk.nodes])
    node_mat = bu.material("HC_Debug_Node", (0.55, 0.55, 0.57), roughness=0.4)
    _add_gn(nodes_obj, _sphere_group(node_radius, node_mat), node_mat)

    by_cat = {}
    for b in sk.beams:
        by_cat.setdefault(category_of(b["mat"], b["type"]), []).append((b["a"], b["b"]))
    counts = {}
    for cat, edges in sorted(by_cat.items()):
        obj = bu.mesh_object(f"PH_Beams_{cat}", verts, edges=edges, col=col)
        color = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["other"])
        mat = bu.material(f"HC_Debug_{cat}", color, roughness=0.5, emission=color, emission_strength=0.35)
        _add_gn(obj, _tube_group(tube_radius, mat), mat)
        obj.color = (*color, 1.0)
        counts[cat] = len(edges)

    if sk.tris:
        faces = [(t["a"], t["b"], t["c"]) for t in sk.tris]
        tri_obj = bu.mesh_object("PH_Tris", verts, faces=faces, col=col)
        tri_obj.display_type = "WIRE"
        tri_obj.hide_render = True
    return {"collection": col.name, "beam_categories": counts}

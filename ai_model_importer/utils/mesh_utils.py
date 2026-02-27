import logging

import bmesh
import bpy

logger = logging.getLogger("ai_model_importer")


def _activate(obj):
    if obj.type != 'MESH':
        raise TypeError(f"Expected MESH, got {obj.type}")
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _enter_edit(obj):
    _activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')


def _to_object():
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _stats(obj):
    return {"poly_count": len(obj.data.polygons), "vert_count": len(obj.data.vertices)}


def _min_bbox_dim(obj):
    bb = obj.bound_box
    xs = [c[0] for c in bb]
    ys = [c[1] for c in bb]
    zs = [c[2] for c in bb]
    return min(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def apply_transforms(obj):
    _activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return "applied"


def merge_duplicates(obj, threshold=0.0001):
    _enter_edit(obj)
    bpy.ops.mesh.select_all(action='SELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    before = len(bm.verts)
    bpy.ops.mesh.remove_doubles(threshold=threshold, use_unselected=False)
    bm = bmesh.from_edit_mesh(obj.data)
    removed = before - len(bm.verts)
    _to_object()
    return f"Removed {removed} vertices"


def recalculate_normals(obj):
    _enter_edit(obj)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    _to_object()
    return "recalculated"


def fix_non_manifold(obj):
    _enter_edit(obj)
    bm = bmesh.from_edit_mesh(obj.data)

    if len(bm.faces) <= 4 or _min_bbox_dim(obj) <= 1e-6:
        _to_object()
        return "skipped"

    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()
    bm = bmesh.from_edit_mesh(obj.data)
    selected = sum(1 for v in bm.verts if v.select)

    if selected > 0:
        bpy.ops.mesh.fill_holes(sides=0)
        detail = f"Filled holes ({selected} non-manifold elements)"
    else:
        detail = "No non-manifold geometry"

    _to_object()
    return detail


def decimate_if_needed(obj, poly_limit=100000):
    _activate(obj)
    count = len(obj.data.polygons)
    if count <= poly_limit:
        return "skipped"
    ratio = poly_limit / count
    mod = obj.modifiers.new(name="AI_Decimate", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=mod.name)
    after = len(obj.data.polygons)
    return f"Decimated {count} -> {after} polys (ratio {ratio:.4f})"


def cleanup_data(obj):
    _activate(obj)

    removed_slots = 0
    for i in range(len(obj.material_slots) - 1, -1, -1):
        if obj.material_slots[i].material is None:
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()
            removed_slots += 1

    _enter_edit(obj)
    bm = bmesh.from_edit_mesh(obj.data)

    degen = [f for f in bm.faces if f.calc_area() < 1e-8]
    rm_faces = len(degen)
    if degen:
        bmesh.ops.delete(bm, geom=degen, context='FACES')

    iso = [v for v in bm.verts if not v.link_edges]
    rm_verts = len(iso)
    if iso:
        bmesh.ops.delete(bm, geom=iso, context='VERTS')

    bmesh.update_edit_mesh(obj.data)
    _to_object()
    return f"Removed {removed_slots} empty slots, {rm_faces} degenerate faces, {rm_verts} isolated verts"


def run_fix_pipeline(obj, settings):
    if obj.type != 'MESH':
        raise TypeError(f"Expected MESH, got {obj.type}")

    results = {}
    steps = [
        ("apply_transforms",    apply_transforms,    True, {}),
        ("merge_by_distance",   merge_duplicates,    settings.fix_merge_doubles,
         {"threshold": settings.merge_threshold}),
        ("recalculate_normals", recalculate_normals,  settings.fix_normals, {}),
        ("fix_non_manifold",    fix_non_manifold,     settings.fix_non_manifold, {}),
        ("decimate_if_needed",  decimate_if_needed,   settings.fix_decimate,
         {"poly_limit": settings.poly_limit}),
        ("cleanup_data",        cleanup_data,         True, {}),
    ]

    for name, func, enabled, kwargs in steps:
        before = _stats(obj)
        if not enabled:
            results[name] = {
                "status": "skipped", "detail": "disabled",
                "before": before, "after": before,
            }
            continue
        try:
            detail = func(obj, **kwargs)
            status = "success"
        except Exception as exc:
            logger.warning("Fix step '%s' failed on '%s': %s", name, obj.name, exc)
            detail = str(exc)
            status = "failed"
            try:
                _to_object()
            except Exception:
                pass

        results[name] = {
            "status": status, "detail": detail,
            "before": before, "after": _stats(obj),
        }

    return results

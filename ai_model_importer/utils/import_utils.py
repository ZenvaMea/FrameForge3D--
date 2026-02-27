import logging
from pathlib import Path

import bpy
from mathutils import Vector

logger = logging.getLogger("ai_model_importer")

SUPPORTED_EXTENSIONS = {
    '.glb', '.gltf', '.fbx', '.obj', '.stl', '.ply',
    '.usd', '.usda', '.usdc', '.usdz',
}

IMPORTERS = {
    '.glb':  lambda p: bpy.ops.import_scene.gltf(filepath=p),
    '.gltf': lambda p: bpy.ops.import_scene.gltf(filepath=p),
    '.fbx':  lambda p: bpy.ops.import_scene.fbx(filepath=p, axis_forward='-Z', axis_up='Y'),
    '.obj':  lambda p: bpy.ops.wm.obj_import(filepath=p),
    '.stl':  lambda p: bpy.ops.wm.stl_import(filepath=p),
    '.ply':  lambda p: bpy.ops.wm.ply_import(filepath=p),
    '.usd':  lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.usda': lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.usdc': lambda p: bpy.ops.wm.usd_import(filepath=p),
    '.usdz': lambda p: bpy.ops.wm.usd_import(filepath=p),
}


def _compute_global_aabb(objects):
    bbox_min = Vector((float('inf'),) * 3)
    bbox_max = Vector((float('-inf'),) * 3)
    found = False

    for obj in objects:
        if not obj or obj.name not in bpy.data.objects:
            continue
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            bbox_min.x = min(bbox_min.x, wc.x)
            bbox_min.y = min(bbox_min.y, wc.y)
            bbox_min.z = min(bbox_min.z, wc.z)
            bbox_max.x = max(bbox_max.x, wc.x)
            bbox_max.y = max(bbox_max.y, wc.y)
            bbox_max.z = max(bbox_max.z, wc.z)
            found = True

    return (bbox_min, bbox_max) if found else (None, None)


def _apply_transform(objects, *, location=False, rotation=False, scale=False):
    valid = [o for o in objects if o and o.name in bpy.data.objects]
    if not valid:
        return
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in valid:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = valid[0]
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)


def auto_center_objects(objects):
    bbox_min, bbox_max = _compute_global_aabb(objects)
    if bbox_min is None:
        return
    center = (bbox_min + bbox_max) / 2.0
    offset = Vector((-center.x, -center.y, -bbox_min.z))
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            obj.location += offset
    _apply_transform(objects, location=True)


def auto_scale_objects(objects, target_size):
    bbox_min, bbox_max = _compute_global_aabb(objects)
    if bbox_min is None:
        return
    dims = bbox_max - bbox_min
    max_dim = max(dims.x, dims.y, dims.z)
    if max_dim <= 0 or abs(max_dim - target_size) < 1e-8:
        return
    factor = target_size / max_dim
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            obj.scale *= factor
    _apply_transform(objects, scale=True)


def separate_objects(objects, mode='BY_LOOSE'):
    """Separate mesh objects by loose parts or by material.

    Args:
        objects: list of imported objects
        mode: 'BY_LOOSE' or 'BY_MATERIAL'

    Returns:
        Updated list of all resulting objects.
    """
    if mode == 'NONE':
        return objects

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh_objects = [o for o in objects if o and o.name in bpy.data.objects and o.type == 'MESH']
    non_mesh = [o for o in objects if o and o.name in bpy.data.objects and o.type != 'MESH']

    if not mesh_objects:
        return objects

    all_new = list(non_mesh)

    for obj in mesh_objects:
        # Skip objects with very few faces (already small parts)
        if len(obj.data.polygons) < 2:
            all_new.append(obj)
            continue

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        before = {o.name for o in bpy.data.objects}

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        if mode == 'BY_MATERIAL':
            bpy.ops.mesh.separate(type='MATERIAL')
        else:
            bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Collect the original + newly split objects
        after_new = [o for o in bpy.data.objects if o.name not in before]
        all_new.append(obj)  # the original (now contains remaining geometry)
        all_new.extend(after_new)

    logger.info("Separated into %d objects (mode=%s)", len(all_new), mode)
    return all_new


def import_single_file(filepath, auto_center=True, auto_scale=True, target_size=2.0, separate_mode='NONE'):
    filepath = str(filepath)
    before = {obj.name for obj in bpy.data.objects}
    new_objects = []
    collection = None

    try:
        ext = Path(filepath).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported format: {ext}")

        importer = IMPORTERS[ext]
        result = importer(filepath)
        if isinstance(result, set) and 'CANCELLED' in result:
            raise RuntimeError("Import cancelled by Blender")

        new_objects = [o for o in bpy.data.objects if o.name not in before]
        if not new_objects:
            raise RuntimeError("No objects were imported")

        col_name = f"AI_Import_{Path(filepath).stem}"
        collection = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(collection)
        for obj in new_objects:
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            collection.objects.link(obj)

        _apply_transform(new_objects, rotation=True, scale=True)

        # Separate into individual parts if requested
        if separate_mode != 'NONE':
            new_objects = separate_objects(new_objects, mode=separate_mode)
            # Re-link separated objects to the import collection
            for obj in new_objects:
                if obj and obj.name in bpy.data.objects:
                    if collection.name not in [c.name for c in obj.users_collection]:
                        for col in list(obj.users_collection):
                            col.objects.unlink(obj)
                        collection.objects.link(obj)

        # Store source directory on each object for texture auto-detection
        source_dir = str(Path(filepath).parent)
        for obj in new_objects:
            if obj and obj.name in bpy.data.objects:
                obj["ai_import_source_dir"] = source_dir

        if auto_center:
            auto_center_objects(new_objects)
        if auto_scale:
            auto_scale_objects(new_objects, target_size)

        logger.info("Imported %d objects from %s", len(new_objects), filepath)
        return {"success": True, "objects": new_objects, "collection": collection, "error": None}

    except Exception as exc:
        logger.error("Failed to import %s: %s", filepath, exc)
        if not new_objects:
            new_objects = [o for o in bpy.data.objects if o.name not in before]
        for obj in list(new_objects):
            if obj and obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        if collection and collection.name in bpy.data.collections:
            bpy.data.collections.remove(collection)
        return {"success": False, "objects": [], "collection": None, "error": str(exc)}

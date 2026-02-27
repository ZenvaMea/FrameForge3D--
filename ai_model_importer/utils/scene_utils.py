import logging
import math
import os

import bmesh
import bpy
from mathutils import Vector

logger = logging.getLogger("ai_model_importer")


def _ensure_object_mode():
    try:
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass


def get_model_bounds(objects):
    bbox_min = Vector((float('inf'),) * 3)
    bbox_max = Vector((float('-inf'),) * 3)
    found = False

    for obj in objects:
        if not obj or obj.name not in bpy.data.objects or obj.type != 'MESH':
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

    if not found:
        return Vector((0, 0, 0)), 1.0

    center = (bbox_min + bbox_max) / 2.0
    diag = (bbox_max - bbox_min).length
    return center, max(diag, 0.001)


def get_or_create_scene_collection():
    name = "AI_Scene_Setup"
    for col in bpy.data.collections:
        if col.name == name:
            return col
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def cleanup_scene_setup():
    """Remove all previously generated scene objects (lights, cameras, empties, backdrop)."""
    col = None
    for c in bpy.data.collections:
        if c.name == "AI_Scene_Setup":
            col = c
            break
    if col is None:
        return

    # Remove all objects in the collection
    for obj in list(col.objects):
        # Clear animation data
        if obj.animation_data and obj.animation_data.action:
            bpy.data.actions.remove(obj.animation_data.action)
        bpy.data.objects.remove(obj, do_unlink=True)

    logger.info("Previous scene setup cleaned up")


def _link_to_scene_col(obj):
    col = get_or_create_scene_collection()
    col.objects.link(obj)


def _add_track_to(obj, target):
    ct = obj.constraints.new('TRACK_TO')
    ct.target = target
    ct.track_axis = 'TRACK_NEGATIVE_Z'
    ct.up_axis = 'UP_Y'


def _create_center_empty(center):
    _ensure_object_mode()
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
    empty = bpy.context.active_object
    empty.name = "AI_Target_Center"
    for col in list(empty.users_collection):
        col.objects.unlink(empty)
    _link_to_scene_col(empty)
    return empty


def setup_studio_lighting(center, D):
    _ensure_object_mode()
    col = get_or_create_scene_collection()
    empty = _create_center_empty(center)

    lights_cfg = [
        ("AI_Key_Light",  (D * 1.5, -D * 1.2, D * 1.8), D * 500, D * 0.5),
        ("AI_Fill_Light", (-D * 1.2, -D * 0.8, D * 1.0), D * 200, D * 0.8),
        ("AI_Rim_Light",  (D * 0.3, D * 1.5, D * 1.5),  D * 300, D * 0.3),
    ]

    for name, pos, energy, size in lights_cfg:
        bpy.ops.object.light_add(type='AREA', location=Vector(pos) + center)
        light = bpy.context.active_object
        light.name = name
        light.data.energy = energy
        light.data.size = size
        _add_track_to(light, empty)
        for c in list(light.users_collection):
            c.objects.unlink(light)
        col.objects.link(light)

    logger.info("Studio lighting created (D=%.2f)", D)
    return empty


def setup_hdri_world(hdri_path=None, strength=1.0, rotation=0.0):
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputWorld')
    output.location = (400, 0)
    bg = nodes.new('ShaderNodeBackground')
    bg.location = (200, 0)
    bg.inputs['Strength'].default_value = strength

    if hdri_path:
        try:
            env_tex = nodes.new('ShaderNodeTexEnvironment')
            env_tex.location = (-100, 0)
            env_tex.image = bpy.data.images.load(hdri_path, check_existing=True)

            mapping = nodes.new('ShaderNodeMapping')
            mapping.location = (-300, 0)
            mapping.inputs['Rotation'].default_value[2] = rotation

            coord = nodes.new('ShaderNodeTexCoord')
            coord.location = (-500, 0)

            links.new(coord.outputs['Generated'], mapping.inputs['Vector'])
            links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
            links.new(env_tex.outputs['Color'], bg.inputs['Color'])
        except Exception:
            logger.warning("Failed to load HDRI: %s", hdri_path)
            bg.inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)
    else:
        bg.inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)

    links.new(bg.outputs['Background'], output.inputs['Surface'])


def create_camera(name, position, center, D):
    _ensure_object_mode()
    col = get_or_create_scene_collection()
    bpy.ops.object.camera_add(location=position)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = 50
    cam.data.clip_start = 0.1
    cam.data.clip_end = D * 20

    empty = None
    for obj in col.objects:
        if obj.name == "AI_Target_Center":
            empty = obj
            break
    if empty is None:
        empty = _create_center_empty(center)
    _add_track_to(cam, empty)

    for c in list(cam.users_collection):
        c.objects.unlink(cam)
    col.objects.link(cam)
    return cam


def setup_turntable(center, D, frames=120, fps=30):
    col = get_or_create_scene_collection()
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames

    sensor_width = 36.0
    focal_length = 50.0
    fov = 2 * math.atan(sensor_width / (2 * focal_length))
    distance = (D / 2) / math.tan(fov / 2) * 1.5
    cam_height = center.z * 1.2 if center.z > 0 else D * 0.8

    _ensure_object_mode()
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
    pivot = bpy.context.active_object
    pivot.name = "AI_Turntable_Pivot"
    for c in list(pivot.users_collection):
        c.objects.unlink(pivot)
    col.objects.link(pivot)

    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, math.radians(360))
    pivot.keyframe_insert(data_path="rotation_euler", frame=frames)

    for fc in pivot.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'LINEAR'

    cam_pos = Vector((center.x, center.y - distance, cam_height))
    cam = create_camera("AI_Turntable_Camera", cam_pos, center, D)
    cam.parent = pivot
    scene.camera = cam
    return cam


def setup_multiview(center, D):
    views = [
        ("AI_Cam_Front", Vector((0, -D * 3, D * 0.8))),
        ("AI_Cam_Back",  Vector((0, D * 3, D * 0.8))),
        ("AI_Cam_Left",  Vector((-D * 3, 0, D * 0.8))),
        ("AI_Cam_Right", Vector((D * 3, 0, D * 0.8))),
        ("AI_Cam_Top",   Vector((0, -D * 0.5, D * 4))),
    ]
    cameras = []
    for name, offset in views:
        cam = create_camera(name, center + offset, center, D)
        cameras.append(cam)

    bpy.context.scene.camera = cameras[0]
    return cameras


def setup_cyclorama_backdrop(center, D, color=(0.8, 0.8, 0.8), texture_path=""):
    """Create a cyclorama (photography studio curved backdrop) around the model.

    Cross-section structure:
        Wall top
           |
           |  Wall (vertical segment)
           |
            \\  Arc transition (16 segments)
             \\_________________ Floor (horizontal segment)
    """
    _ensure_object_mode()

    # Clean up previous backdrop
    BACKDROP_NAME = "AI_Cyclorama_Backdrop"
    BACKDROP_MAT_NAME = "AI_Cyclorama_Material"
    for obj in list(bpy.data.objects):
        if obj.name.startswith(BACKDROP_NAME):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Backdrop is always anchored at the origin (floor at z=0)
    # so it aligns with the imported model which is auto-centered
    origin_x = 0.0
    origin_y = 0.0
    floor_z = 0.0

    # Dimensions based on D (large enough to fill any camera angle)
    floor_front = D * 6.0      # how far floor extends in front (-Y)
    floor_back = D * 2.0       # floor behind the arc start (+Y)
    side_extent = D * 5.0      # half-width (left/right)
    wall_height = D * 5.0      # vertical wall height (above arc)
    arc_radius = D * 1.2       # radius of the curved transition
    arc_segments = 16

    # Build cross-section profile (in YZ plane, extruded along X)
    # Going from front-floor → arc → wall-top
    profile_points = []

    # Floor: from front to arc start (along -Y to +Y)
    floor_y_start = origin_y - floor_front
    floor_y_end = origin_y + floor_back
    arc_center_y = floor_y_end
    arc_center_z = floor_z + arc_radius

    # Floor segment
    profile_points.append((floor_y_start, floor_z))
    profile_points.append((floor_y_end, floor_z))

    # Arc segment (quarter circle from floor to wall)
    for i in range(1, arc_segments + 1):
        angle = (math.pi / 2) * (i / arc_segments)
        py = arc_center_y + arc_radius * math.sin(angle)
        pz = arc_center_z - arc_radius * math.cos(angle)
        profile_points.append((py, pz))

    # Wall segment (vertical, from arc top to wall top)
    wall_y = arc_center_y + arc_radius
    wall_top_z = arc_center_z + wall_height
    profile_points.append((wall_y, wall_top_z))

    # Create mesh with bmesh
    bm = bmesh.new()

    num_profile = len(profile_points)
    # Two side edges: left and right
    x_left = origin_x - side_extent
    x_right = origin_x + side_extent

    left_verts = []
    right_verts = []
    for (py, pz) in profile_points:
        lv = bm.verts.new((x_left, py, pz))
        rv = bm.verts.new((x_right, py, pz))
        left_verts.append(lv)
        right_verts.append(rv)

    bm.verts.ensure_lookup_table()

    # Create faces between consecutive profile segments
    for i in range(num_profile - 1):
        v0 = left_verts[i]
        v1 = left_verts[i + 1]
        v2 = right_verts[i + 1]
        v3 = right_verts[i]
        bm.faces.new((v0, v1, v2, v3))

    bm.faces.ensure_lookup_table()

    # UV layer
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # Calculate cumulative arc lengths along profile for V coordinate
    arc_lengths = [0.0]
    for i in range(1, num_profile):
        dy = profile_points[i][0] - profile_points[i - 1][0]
        dz = profile_points[i][1] - profile_points[i - 1][1]
        arc_lengths.append(arc_lengths[-1] + math.sqrt(dy * dy + dz * dz))
    total_length = arc_lengths[-1] if arc_lengths[-1] > 0 else 1.0

    for face in bm.faces:
        for loop in face.loops:
            vert = loop.vert
            # U: 0 at left, 1 at right
            u = (vert.co.x - x_left) / (x_right - x_left) if x_right != x_left else 0.5
            # V: based on arc length position
            # Find which profile point this vertex corresponds to
            idx = None
            for j, (lv, rv) in enumerate(zip(left_verts, right_verts)):
                if vert == lv or vert == rv:
                    idx = j
                    break
            v = arc_lengths[idx] / total_length if idx is not None else 0.0
            loop[uv_layer].uv = (u, v)

    # Create mesh object
    mesh = bpy.data.meshes.new(BACKDROP_NAME)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(BACKDROP_NAME, mesh)
    col = get_or_create_scene_collection()
    col.objects.link(obj)

    # Smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Material setup
    mat = bpy.data.materials.get(BACKDROP_MAT_NAME)
    if mat:
        bpy.data.materials.remove(mat)
    mat = bpy.data.materials.new(BACKDROP_MAT_NAME)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output_node = nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (400, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    bsdf.inputs['Roughness'].default_value = 0.9

    if texture_path and os.path.isfile(texture_path):
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.location = (-400, 0)
        tex_node.image = bpy.data.images.load(texture_path, check_existing=True)
        uv_node = nodes.new('ShaderNodeTexCoord')
        uv_node.location = (-600, 0)
        links.new(uv_node.outputs['UV'], tex_node.inputs['Vector'])
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)

    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
    obj.data.materials.append(mat)

    logger.info("Cyclorama backdrop created (D=%.2f)", D)
    return obj

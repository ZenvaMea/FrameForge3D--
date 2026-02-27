import logging
import math
import os
import re

import bpy

logger = logging.getLogger("ai_model_importer")

TEXTURE_PATTERNS = [
    ("ALBEDO",    re.compile(r"(?i)(base.?color|albedo|diffuse|_col_|_diff_)")),
    ("NORMAL",    re.compile(r"(?i)(normal|_norm_|_nrm_|_nor_)")),
    ("ROUGHNESS", re.compile(r"(?i)(rough|roughness|_rgh_)")),
    ("METALLIC",  re.compile(r"(?i)(metal|metallic|_met_)")),
    ("AO",        re.compile(r"(?i)(ao|ambient.?occ|occlusion|_occ_)")),
    ("HEIGHT",    re.compile(r"(?i)(height|bump|displacement|_disp_|_hgt_)")),
    ("EMISSION",  re.compile(r"(?i)(emiss|emission|glow|_emit_)")),
    ("OPACITY",   re.compile(r"(?i)(opacity|alpha|_alp_|transparency)")),
]

SRGB_TYPES = {"ALBEDO", "EMISSION"}


def detect_material_state(obj):
    if not obj.data.materials:
        if obj.data.color_attributes:
            return "HAS_VERTEX_COLORS"
        return "BARE"

    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    return "HAS_TEXTURES"
    return "HAS_MATERIALS_NO_TEX"


def detect_texture_type(image_name):
    for tex_type, pattern in TEXTURE_PATTERNS:
        if pattern.search(image_name):
            return tex_type
    return None


def ensure_correct_colorspace(image_node, texture_type):
    if not image_node or not image_node.image:
        return
    cs = "sRGB" if texture_type in SRGB_TYPES else "Non-Color"
    image_node.image.colorspace_settings.name = cs


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff', '.tif', '.exr', '.hdr'}

# Map texture type -> Principled BSDF input name
TEXTURE_TO_BSDF_INPUT = {
    "ALBEDO":    "Base Color",
    "METALLIC":  "Metallic",
    "ROUGHNESS": "Roughness",
    "NORMAL":    None,       # needs Normal Map node
    "EMISSION":  "Emission Color",
    "OPACITY":   "Alpha",
    "AO":        None,       # mixed into base color
    "HEIGHT":    None,       # needs Displacement node
}


def find_textures_near_file(source_dir):
    """Scan a directory for texture images and classify them by PBR type."""
    if not source_dir or not os.path.isdir(source_dir):
        return {}

    found = {}  # tex_type -> filepath
    for fn in os.listdir(source_dir):
        ext = os.path.splitext(fn)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        tex_type = detect_texture_type(fn)
        if tex_type and tex_type not in found:
            found[tex_type] = os.path.join(source_dir, fn)

    return found


def create_pbr_material_from_textures(obj, textures):
    """Create a Principled BSDF material with PBR texture maps connected.

    Args:
        obj: the mesh object
        textures: dict of {tex_type: filepath}
    """
    mat = bpy.data.materials.new(name=f"AI_PBR_{obj.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)

    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    x_offset = -400
    y_offset = 300

    for tex_type, filepath in textures.items():
        try:
            img = bpy.data.images.load(filepath, check_existing=True)
        except Exception:
            logger.warning("Failed to load texture: %s", filepath)
            continue

        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.location = (x_offset, y_offset)
        tex_node.image = img
        tex_node.label = tex_type
        ensure_correct_colorspace(tex_node, tex_type)

        bsdf_input = TEXTURE_TO_BSDF_INPUT.get(tex_type)

        if tex_type == "NORMAL":
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.location = (x_offset + 300, y_offset)
            links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
        elif tex_type == "HEIGHT":
            disp = nodes.new('ShaderNodeDisplacement')
            disp.location = (x_offset + 300, y_offset)
            disp.inputs['Scale'].default_value = 0.05
            links.new(tex_node.outputs['Color'], disp.inputs['Height'])
            links.new(disp.outputs['Displacement'], output.inputs['Displacement'])
        elif tex_type == "OPACITY":
            links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'CLIP'
        elif bsdf_input:
            links.new(tex_node.outputs['Color'], bsdf.inputs[bsdf_input])

        y_offset -= 300

    # Clear existing materials and assign new one
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    logger.info("Created PBR material with %d textures for %s", len(textures), obj.name)
    return mat


def create_vertex_color_material(obj):
    mat = bpy.data.materials.new(name=f"AI_VertexColor_{obj.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)

    attr = nodes.new('ShaderNodeVertexColor')
    attr.location = (-200, 0)
    layer_name = obj.data.color_attributes[0].name if obj.data.color_attributes else "Col"
    attr.layer_name = layer_name

    links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    obj.data.materials.append(mat)
    return mat


def create_default_material():
    name = "AI_Default_Material"
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
        bsdf.inputs['Metallic'].default_value = 0.0
        bsdf.inputs['Roughness'].default_value = 0.5
        bsdf.inputs['IOR'].default_value = 1.45
        bsdf.inputs['Specular IOR Level'].default_value = 0.5
    return mat


def generate_smart_uv(obj):
    if len(obj.data.uv_layers) > 0:
        return
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(
        angle_limit=math.radians(66),
        island_margin=0.02,
        correct_aspect=True,
        scale_to_bounds=True,
    )
    bpy.ops.object.mode_set(mode='OBJECT')


def setup_alpha_material(material):
    if not material or not material.use_nodes:
        return
    material.blend_method = 'BLEND'
    material.shadow_method = 'CLIP'


def setup_materials_for_object(obj, settings):
    if obj.type != 'MESH':
        return "not_mesh"

    state = detect_material_state(obj)

    if state == "HAS_TEXTURES":
        logger.info("Preserving existing textures on %s", obj.name)
        return "preserved"

    # Try auto-detecting textures from source directory
    if settings.auto_detect_textures and state in ("BARE", "HAS_MATERIALS_NO_TEX"):
        source_dir = obj.get("ai_import_source_dir", "")
        if source_dir:
            textures = find_textures_near_file(source_dir)
            if textures:
                if settings.smart_uv:
                    generate_smart_uv(obj)
                create_pbr_material_from_textures(obj, textures)
                logger.info("Auto-detected %d textures for %s", len(textures), obj.name)
                return "auto_detected"

    if state == "HAS_MATERIALS_NO_TEX":
        logger.info("Preserving existing materials on %s", obj.name)
        return "preserved"

    if state == "HAS_VERTEX_COLORS" and settings.vertex_color_convert:
        create_vertex_color_material(obj)
        logger.info("Created vertex color material for %s", obj.name)
        return "vertex_color"

    # BARE
    if settings.smart_uv:
        generate_smart_uv(obj)
    mat = create_default_material()
    obj.data.materials.append(mat)
    logger.info("Applied default material to %s", obj.name)
    return "default"

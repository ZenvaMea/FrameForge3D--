bl_info = {
    "name": "FrameForge 3D - 首尾帧生成器",
    "author": "米醋电子工作室崔师傅",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > FrameForge",
    "description": "一键导入、修复、布光渲染3D模型，生成AI视频制作所需的首尾帧",
    "category": "Import-Export",
}

import logging

import bpy
from bpy.props import EnumProperty, StringProperty

from .properties import AIImporterProperties
from .operators.import_ops import AIIMPORT_OT_import_model, AIIMPORT_OT_import_folder
from .operators.fix_ops import AIIMPORT_OT_fix_model
from .operators.material_ops import AIIMPORT_OT_setup_materials
from .operators.scene_ops import AIIMPORT_OT_setup_scene
from .operators.render_ops import AIIMPORT_OT_render
from .operators.batch_ops import AIIMPORT_OT_batch_process, AIIMPORT_OT_batch_cancel
from .panels.main_panel import (
    AIIMPORT_PT_main_panel,
    AIIMPORT_PT_import_panel,
    AIIMPORT_PT_fix_panel,
    AIIMPORT_PT_material_panel,
    AIIMPORT_PT_scene_panel,
    AIIMPORT_PT_render_panel,
    AIIMPORT_PT_batch_panel,
)

logger = logging.getLogger("ai_model_importer")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[FrameForge] [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class AIImporterPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    default_output_path: StringProperty(
        name="Default Output Path",
        subtype='DIR_PATH',
    )
    default_render_preset: EnumProperty(
        name="Default Render Preset",
        items=[
            ('PREVIEW', "Quick Preview", ""),
            ('PRODUCT', "Product", ""),
            ('BATCH', "Batch", ""),
            ('DIGITAL_TWIN', "Digital Twin", ""),
        ],
        default='PREVIEW',
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_output_path")
        layout.prop(self, "default_render_preset")


classes = [
    AIImporterProperties,
    AIImporterPreferences,
    AIIMPORT_OT_import_model,
    AIIMPORT_OT_import_folder,
    AIIMPORT_OT_fix_model,
    AIIMPORT_OT_setup_materials,
    AIIMPORT_OT_setup_scene,
    AIIMPORT_OT_render,
    AIIMPORT_OT_batch_process,
    AIIMPORT_OT_batch_cancel,
    AIIMPORT_PT_main_panel,
    AIIMPORT_PT_import_panel,
    AIIMPORT_PT_fix_panel,
    AIIMPORT_PT_material_panel,
    AIIMPORT_PT_scene_panel,
    AIIMPORT_PT_render_panel,
    AIIMPORT_PT_batch_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ai_importer = bpy.props.PointerProperty(type=AIImporterProperties)
    logger.info("AI Model Importer registered")


def unregister():
    del bpy.types.Scene.ai_importer
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    logger.info("AI Model Importer unregistered")

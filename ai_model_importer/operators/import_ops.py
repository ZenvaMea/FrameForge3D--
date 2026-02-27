import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..utils.import_utils import SUPPORTED_EXTENSIONS, import_single_file


class AIIMPORT_OT_import_model(bpy.types.Operator, ImportHelper):
    bl_idname = "aiimport.import_model"
    bl_label = "导入AI模型"
    bl_description = "选择一个3D模型文件导入到场景中"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.glb;*.gltf;*.fbx;*.obj;*.stl;*.ply;*.usd;*.usda;*.usdc;*.usdz",
        options={'HIDDEN'},
    )

    def execute(self, context):
        props = context.scene.ai_importer
        result = import_single_file(
            self.filepath,
            auto_center=props.auto_center,
            auto_scale=props.auto_scale,
            target_size=props.target_size,
            separate_mode=props.auto_separate,
        )

        if result["success"]:
            count = len(result["objects"])
            self.report({'INFO'}, f"导入成功！共 {count} 个对象")
        else:
            self.report({'ERROR'}, f"导入失败：{result['error']}")
        return {'FINISHED'} if result["success"] else {'CANCELLED'}


class AIIMPORT_OT_import_folder(bpy.types.Operator):
    bl_idname = "aiimport.import_folder"
    bl_label = "选择模型文件夹"
    bl_description = "选择一个包含多个模型的文件夹"
    bl_options = {'REGISTER'}

    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.scene.ai_importer.batch_input_dir = self.directory
        self.report({'INFO'}, f"已选择文件夹：{self.directory}")
        return {'FINISHED'}

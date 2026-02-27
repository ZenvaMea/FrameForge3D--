import bpy

from ..utils.mesh_utils import run_fix_pipeline


class AIIMPORT_OT_fix_model(bpy.types.Operator):
    bl_idname = "aiimport.fix_model"
    bl_label = "修复模型"
    bl_description = "自动修复选中模型的常见问题（重叠顶点、法线、破面等）"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        props = context.scene.ai_importer
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        total_fixed = 0

        for obj in meshes:
            results = run_fix_pipeline(obj, props)
            failures = sum(1 for r in results.values() if r["status"] == "failed")
            if failures:
                self.report({'WARNING'}, f"{obj.name}：有 {failures} 个步骤失败")
            else:
                self.report({'INFO'}, f"{obj.name}：修复完成")
            total_fixed += 1

        self.report({'INFO'}, f"已修复 {total_fixed} 个模型")
        return {'FINISHED'}

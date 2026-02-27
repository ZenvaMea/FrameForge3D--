import bpy

from ..utils.material_utils import setup_materials_for_object


class AIIMPORT_OT_setup_materials(bpy.types.Operator):
    bl_idname = "aiimport.setup_materials"
    bl_label = "设置材质"
    bl_description = "自动检测并设置PBR材质"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        props = context.scene.ai_importer
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        results = {"preserved": 0, "vertex_color": 0, "default": 0, "auto_detected": 0}

        for obj in meshes:
            state = setup_materials_for_object(obj, props)
            results[state] = results.get(state, 0) + 1

        parts = []
        if results["auto_detected"]:
            parts.append(f"{results['auto_detected']} 个自动检测贴图")
        if results["preserved"]:
            parts.append(f"{results['preserved']} 个保留原材质")
        if results["vertex_color"]:
            parts.append(f"{results['vertex_color']} 个转换顶点色")
        if results["default"]:
            parts.append(f"{results['default']} 个赋予默认材质")

        self.report({'INFO'}, f"材质设置完成：{'，'.join(parts) or '无变化'}")
        return {'FINISHED'}

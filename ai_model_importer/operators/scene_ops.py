import bpy

from ..utils.scene_utils import (
    cleanup_scene_setup,
    create_camera,
    get_model_bounds,
    setup_cyclorama_backdrop,
    setup_hdri_world,
    setup_multiview,
    setup_studio_lighting,
    setup_turntable,
)
from mathutils import Vector


class AIIMPORT_OT_setup_scene(bpy.types.Operator):
    bl_idname = "aiimport.setup_scene"
    bl_label = "配置场景"
    bl_description = "自动配置灯光、相机和环境"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        props = context.scene.ai_importer
        # Only use MESH objects for bounds calculation (ignore lights, cameras, etc.)
        objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        try:
            # Clean up previous scene setup first
            cleanup_scene_setup()

            center, D = get_model_bounds(objects)

            if props.lighting_preset == 'STUDIO':
                setup_studio_lighting(center, D)
            elif props.lighting_preset == 'HDRI':
                hdri = props.hdri_path if props.hdri_path else None
                setup_hdri_world(hdri, props.hdri_strength, props.hdri_rotation)
            else:
                setup_hdri_world(None, 1.0, 0.0)

            if props.camera_preset == 'FRONT':
                cam = create_camera("AI_Cam_Front",
                                    center + Vector((0, -D * 3, D * 0.8)), center, D)
                context.scene.camera = cam
            elif props.camera_preset == 'THREE_QUARTER':
                cam = create_camera("AI_Cam_ThreeQuarter",
                                    center + Vector((D * 2.5, -D * 2.5, D * 1.5)), center, D)
                context.scene.camera = cam
            elif props.camera_preset == 'TURNTABLE':
                setup_turntable(center, D, props.turntable_frames, fps=30)
            elif props.camera_preset == 'MULTIVIEW':
                setup_multiview(center, D)

            if props.use_backdrop:
                setup_cyclorama_backdrop(
                    center, D,
                    color=props.backdrop_color,
                    texture_path=props.backdrop_texture,
                )

        except Exception as exc:
            self.report({'ERROR'}, f"场景配置失败：{exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, "场景配置完成！可以按 Numpad 0 查看相机视角")
        return {'FINISHED'}

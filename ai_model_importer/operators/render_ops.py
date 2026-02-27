import logging
import os

import bpy

from ..presets.render_presets import RENDER_PRESETS

logger = logging.getLogger("ai_model_importer")


def apply_render_preset(scene, preset_name):
    preset = RENDER_PRESETS.get(preset_name)
    if not preset:
        return

    scene.render.engine = preset['engine']
    scene.render.resolution_x = preset['resolution_x']
    scene.render.resolution_y = preset['resolution_y']
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = preset['film_transparent']
    scene.render.image_settings.file_format = preset['file_format']
    scene.render.image_settings.color_depth = preset['color_depth']
    scene.render.image_settings.color_mode = preset['color_mode']

    view = scene.view_settings
    view.view_transform = preset['color_management']

    if preset['engine'] == 'CYCLES':
        scene.cycles.samples = preset['samples']
        scene.cycles.use_denoising = preset['use_denoise']
    elif preset['engine'] == 'BLENDER_EEVEE_NEXT':
        scene.eevee.taa_render_samples = preset['samples']


def detect_gpu():
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for device_type in ('CUDA', 'HIP', 'ONEAPI'):
            try:
                prefs.compute_device_type = device_type
                prefs.get_devices()
                gpu_devices = [d for d in prefs.devices if d.type != 'CPU']
                if gpu_devices:
                    for d in prefs.devices:
                        d.use = True
                    denoiser = 'OPENIMAGEDENOISE'
                    if device_type == 'CUDA':
                        try:
                            bpy.context.scene.cycles.denoiser = 'OPTIX'
                            denoiser = 'OPTIX'
                        except Exception:
                            pass
                    return {'device': 'GPU', 'type': device_type, 'denoiser': denoiser}
            except Exception:
                continue
    except Exception:
        pass
    return {'device': 'CPU', 'type': 'CPU', 'denoiser': 'OPENIMAGEDENOISE'}


def get_output_path(model_name, preset, view, output_dir):
    if view == 'turntable':
        filename = f"{model_name}_turntable_"
    elif view:
        filename = f"{model_name}_{view}.png"
    else:
        filename = f"{model_name}_{preset}.png"

    path = os.path.join(output_dir, filename)

    if view != 'turntable' and os.path.exists(path):
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base}_{counter:03d}{ext}"):
            counter += 1
        path = f"{base}_{counter:03d}{ext}"

    return path


class AIIMPORT_OT_render(bpy.types.Operator):
    bl_idname = "aiimport.render"
    bl_label = "渲染"
    bl_description = "使用当前设置渲染图片"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.ai_importer
        scene = context.scene

        try:
            apply_render_preset(scene, props.render_preset)

            if props.render_preset == 'PRODUCT':
                gpu_info = detect_gpu()
                scene.cycles.device = gpu_info['device']
                scene.cycles.denoiser = gpu_info['denoiser']

            output_dir = props.output_path or bpy.app.tempdir
            os.makedirs(output_dir, exist_ok=True)

            cam_name = scene.camera.name if scene.camera else "render"
            is_turntable = "turntable" in cam_name.lower()

            if is_turntable:
                out = get_output_path(cam_name, props.render_preset, 'turntable', output_dir)
                scene.render.filepath = out
                bpy.ops.render.render(animation=True)
                self.report({'INFO'}, f"转盘动画渲染完成：{out}")
            else:
                out = get_output_path(cam_name, props.render_preset, None, output_dir)
                scene.render.filepath = out
                bpy.ops.render.render(write_still=True)
                self.report({'INFO'}, f"渲染完成：{out}")

        except Exception as exc:
            self.report({'ERROR'}, f"渲染失败：{exc}")
            return {'CANCELLED'}

        return {'FINISHED'}

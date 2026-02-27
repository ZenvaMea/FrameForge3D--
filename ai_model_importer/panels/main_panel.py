import bpy


class AIIMPORT_PT_main_panel(bpy.types.Panel):
    bl_label = "FrameForge 3D"
    bl_idname = "AIIMPORT_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"

    def draw(self, context):
        self.layout.label(text="首尾帧生成器 v1.0 · 米醋电子工作室")


class AIIMPORT_PT_import_panel(bpy.types.Panel):
    bl_label = "① 导入模型"
    bl_idname = "AIIMPORT_PT_import_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.operator("aiimport.import_model", text="选择模型文件导入", icon='IMPORT')
        layout.separator()
        layout.prop(props, "auto_center")
        row = layout.row()
        row.prop(props, "auto_scale")
        sub = row.row()
        sub.active = props.auto_scale
        sub.prop(props, "target_size")
        layout.prop(props, "auto_separate")


class AIIMPORT_PT_fix_panel(bpy.types.Panel):
    bl_label = "② 自动修复"
    bl_idname = "AIIMPORT_PT_fix_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.label(text="先选中模型，再点修复", icon='INFO')
        layout.separator()

        row = layout.row()
        row.prop(props, "fix_merge_doubles")
        sub = row.row()
        sub.active = props.fix_merge_doubles
        sub.prop(props, "merge_threshold")

        layout.prop(props, "fix_normals")
        layout.prop(props, "fix_non_manifold")

        row = layout.row()
        row.prop(props, "fix_decimate")
        sub = row.row()
        sub.active = props.fix_decimate
        sub.prop(props, "poly_limit")

        layout.separator()
        layout.operator("aiimport.fix_model", text="一键修复模型", icon='MODIFIER')


class AIIMPORT_PT_material_panel(bpy.types.Panel):
    bl_label = "③ 材质设置"
    bl_idname = "AIIMPORT_PT_material_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.label(text="先选中模型，再点设置材质", icon='INFO')
        layout.separator()
        layout.prop(props, "auto_detect_textures")
        layout.prop(props, "smart_uv")
        layout.prop(props, "vertex_color_convert")
        layout.separator()
        layout.operator("aiimport.setup_materials", text="自动设置材质", icon='MATERIAL')


class AIIMPORT_PT_scene_panel(bpy.types.Panel):
    bl_label = "④ 灯光和相机"
    bl_idname = "AIIMPORT_PT_scene_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.label(text="先选中模型，再点配置场景", icon='INFO')
        layout.separator()

        box = layout.box()
        box.label(text="灯光：", icon='LIGHT')
        box.prop(props, "lighting_preset", text="")
        if props.lighting_preset == 'HDRI':
            box.prop(props, "hdri_path")
            box.prop(props, "hdri_strength")
            box.prop(props, "hdri_rotation")

        layout.separator()

        box = layout.box()
        box.label(text="相机角度：", icon='CAMERA_DATA')
        box.prop(props, "camera_preset", text="")
        if props.camera_preset == 'TURNTABLE':
            box.prop(props, "turntable_frames")

        layout.separator()

        box = layout.box()
        box.label(text="背景：", icon='WORLD')
        box.prop(props, "use_backdrop")
        if props.use_backdrop:
            box.prop(props, "backdrop_color")
            box.prop(props, "backdrop_texture")

        layout.separator()
        layout.operator("aiimport.setup_scene", text="一键配置场景", icon='SCENE')


class AIIMPORT_PT_render_panel(bpy.types.Panel):
    bl_label = "⑤ 渲染出图"
    bl_idname = "AIIMPORT_PT_render_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.prop(props, "render_preset", text="质量")
        row = layout.row(align=True)
        row.prop(props, "resolution_x")
        row.prop(props, "resolution_y")
        layout.prop(props, "output_path")
        layout.separator()
        layout.operator("aiimport.render", text="开始渲染", icon='RENDER_STILL')


class AIIMPORT_PT_batch_panel(bpy.types.Panel):
    bl_label = "⑥ 批量处理"
    bl_idname = "AIIMPORT_PT_batch_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FrameForge"
    bl_parent_id = "AIIMPORT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_importer

        layout.prop(props, "batch_input_dir")
        layout.operator("aiimport.import_folder", text="选择模型文件夹", icon='FILE_FOLDER')
        layout.prop(props, "batch_output_dir")
        layout.prop(props, "batch_recursive")

        layout.separator()
        layout.label(text="处理步骤：")
        col = layout.column(align=True)
        col.prop(props, "batch_do_import")
        col.prop(props, "batch_do_fix")
        col.prop(props, "batch_do_material")
        col.prop(props, "batch_do_render")

        layout.separator()
        if props.batch_progress > 0 and props.batch_progress < 100:
            layout.label(text=f"进度：{props.batch_progress:.0f}%")
            if props.batch_current_file:
                layout.label(text=f"正在处理：{props.batch_current_file}")
            layout.operator("aiimport.batch_cancel", text="停止", icon='CANCEL')
        else:
            layout.operator("aiimport.batch_process", text="开始批量处理", icon='PLAY')

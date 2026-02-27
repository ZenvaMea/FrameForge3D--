import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


class AIImporterProperties(PropertyGroup):

    # -- 导入设置 --
    auto_center: BoolProperty(name="自动居中", description="导入后自动移到场景中心", default=True)
    auto_scale: BoolProperty(name="自动缩放", description="导入后自动缩放到合适大小", default=True)
    target_size: FloatProperty(
        name="目标尺寸", description="模型最长边的目标长度（米）",
        default=2.0, min=0.1, max=100.0, unit='LENGTH',
    )
    import_path: StringProperty(name="导入路径", subtype='FILE_PATH')
    auto_separate: EnumProperty(
        name="自动分离",
        description="导入后自动拆分为多个独立对象，方便单独编辑和上材质",
        items=[
            ('NONE', "不分离", "保持原样，导入什么就是什么"),
            ('BY_MATERIAL', "按材质分离", "根据材质槽拆分，同材质的面成为一个对象"),
            ('BY_LOOSE', "按独立块分离", "把不相连的网格块各自拆成独立对象"),
        ],
        default='BY_LOOSE',
    )

    # -- 修复设置 --
    fix_merge_doubles: BoolProperty(name="合并重叠顶点", description="移除重叠的顶点", default=True)
    merge_threshold: FloatProperty(
        name="合并距离", description="小于此距离的顶点会被合并",
        default=0.0001, min=0.00001, max=0.01, precision=5, step=0.001,
    )
    fix_normals: BoolProperty(name="修复法线", description="让所有面的法线朝外", default=True)
    fix_non_manifold: BoolProperty(name="修复破面", description="填补模型上的破洞", default=True)
    fix_decimate: BoolProperty(name="自动减面", description="面数过多时自动降低", default=True)
    poly_limit: IntProperty(
        name="面数上限", description="超过此数量会自动减面",
        default=100000, min=1000, max=10000000,
    )

    # -- 材质设置 --
    auto_detect_textures: BoolProperty(name="自动检测贴图", default=True)
    smart_uv: BoolProperty(name="自动UV展开", description="没有UV的模型自动生成UV", default=True)
    vertex_color_convert: BoolProperty(name="转换顶点色", description="把顶点颜色转为材质", default=True)

    # -- 场景设置 --
    lighting_preset: EnumProperty(
        name="灯光方案",
        items=[
            ('STUDIO', "影棚灯光", "专业三点布光，适合产品展示"),
            ('HDRI', "环境光(HDRI)", "使用HDRI图片做环境照明"),
            ('NONE', "不设置", "不添加灯光"),
        ],
    )
    camera_preset: EnumProperty(
        name="相机角度",
        items=[
            ('FRONT', "正面", "从正前方看模型"),
            ('THREE_QUARTER', "3/4侧面", "经典产品展示角度"),
            ('TURNTABLE', "转盘动画", "360度旋转展示"),
            ('MULTIVIEW', "多角度", "前后左右上 5个角度"),
            ('NONE', "不设置", "不添加相机"),
        ],
    )
    hdri_path: StringProperty(name="HDRI文件", subtype='FILE_PATH')
    hdri_strength: FloatProperty(
        name="环境光强度", default=1.0, min=0.0, max=10.0,
    )
    hdri_rotation: FloatProperty(
        name="环境旋转", default=0.0, min=0.0, max=6.283185, subtype='ANGLE',
    )
    turntable_frames: IntProperty(
        name="转盘帧数", description="转一圈的总帧数，越多越慢越平滑",
        default=120, min=24, max=600,
    )

    # -- 背景设置 --
    use_backdrop: BoolProperty(name="启用背景", description="添加摄影棚弧形背景", default=False)
    backdrop_color: FloatVectorProperty(
        name="背景颜色", description="弧形背景的颜色",
        subtype='COLOR', default=(0.8, 0.8, 0.8), min=0.0, max=1.0,
    )
    backdrop_texture: StringProperty(name="背景贴图", description="可选的背景贴图文件", subtype='FILE_PATH')

    # -- 渲染设置 --
    render_preset: EnumProperty(
        name="渲染质量",
        items=[
            ('PREVIEW', "快速预览", "速度快，画质一般（EEVEE 1280x720）"),
            ('PRODUCT', "产品级", "画质最好，速度慢（Cycles 1920x1080）"),
            ('BATCH', "批量模式", "平衡画质和速度（EEVEE 1920x1080）"),
            ('DIGITAL_TWIN', "数字孪生", "实时预览用"),
        ],
    )
    output_path: StringProperty(name="输出文件夹", subtype='DIR_PATH')
    resolution_x: IntProperty(name="宽度", default=1920, min=320, max=7680)
    resolution_y: IntProperty(name="高度", default=1080, min=240, max=4320)

    # -- 批量处理 --
    batch_input_dir: StringProperty(name="模型文件夹", subtype='DIR_PATH')
    batch_output_dir: StringProperty(name="输出文件夹", subtype='DIR_PATH')
    batch_recursive: BoolProperty(name="包含子文件夹", default=False)
    batch_do_import: BoolProperty(name="导入", default=True)
    batch_do_fix: BoolProperty(name="修复", default=True)
    batch_do_material: BoolProperty(name="材质", default=True)
    batch_do_render: BoolProperty(name="渲染", default=True)
    batch_progress: FloatProperty(
        name="进度", default=0.0, min=0.0, max=100.0, options={'HIDDEN'},
    )
    batch_current_file: StringProperty(name="当前文件", default="")

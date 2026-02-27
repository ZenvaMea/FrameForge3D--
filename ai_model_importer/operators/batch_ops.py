import logging
import os
import time
import uuid

import bpy

from ..utils.import_utils import SUPPORTED_EXTENSIONS, import_single_file
from ..utils.material_utils import setup_materials_for_object
from ..utils.mesh_utils import run_fix_pipeline
from ..utils.report_utils import generate_batch_report, generate_fix_report
from ..utils.scene_utils import cleanup_scene_setup, get_model_bounds, setup_cyclorama_backdrop, setup_hdri_world, setup_studio_lighting
from ..operators.render_ops import apply_render_preset, detect_gpu, get_output_path

logger = logging.getLogger("ai_model_importer")

STAGES = ['import', 'fix', 'material', 'scene', 'render', 'cleanup']


def scan_directory(input_dir, recursive=False):
    files = []
    if recursive:
        for root, _dirs, filenames in os.walk(input_dir):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, fn))
    else:
        for fn in os.listdir(input_dir):
            full = os.path.join(input_dir, fn)
            if os.path.isfile(full) and os.path.splitext(fn)[1].lower() in SUPPORTED_EXTENSIONS:
                files.append(full)
    return sorted(files, key=lambda p: os.path.basename(p).lower())


class BatchState:
    _instance = None

    def __init__(self):
        self.file_list = []
        self.current_index = 0
        self.current_stage = 0
        self.cancelled = False
        self.results = []
        self.start_time = 0.0
        self.model_start_time = 0.0
        self.current_import_result = None
        self.batch_id = str(uuid.uuid4())

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = cls()
        return cls._instance


def _batch_timer():
    state = BatchState.get()
    props = bpy.context.scene.ai_importer

    if state.cancelled or state.current_index >= len(state.file_list):
        _finalize_batch(state, props)
        return None

    filepath = state.file_list[state.current_index]
    filename = os.path.basename(filepath)
    stage = STAGES[state.current_stage]
    total = len(state.file_list)
    idx = state.current_index + 1

    bpy.context.workspace.status_text_set(f"Processing {idx}/{total}: {filename} [{stage}]")
    props.batch_progress = (state.current_index / total) * 100
    props.batch_current_file = filename

    try:
        if stage == 'import':
            state.model_start_time = time.time()
            if props.batch_do_import:
                result = import_single_file(filepath, props.auto_center, props.auto_scale, props.target_size, props.auto_separate)
                state.current_import_result = result
                if not result["success"]:
                    _skip_model(state, filepath, result["error"])
                    return 0.01
            else:
                state.current_import_result = {"success": False, "objects": [], "error": "import_disabled"}

        elif stage == 'fix':
            if props.batch_do_fix and state.current_import_result and state.current_import_result["success"]:
                for obj in state.current_import_result["objects"]:
                    if obj.type == 'MESH':
                        run_fix_pipeline(obj, props)

        elif stage == 'material':
            if props.batch_do_material and state.current_import_result and state.current_import_result["success"]:
                for obj in state.current_import_result["objects"]:
                    setup_materials_for_object(obj, props)

        elif stage == 'scene':
            if state.current_import_result and state.current_import_result["success"]:
                cleanup_scene_setup()
                objects = state.current_import_result["objects"]
                center, D = get_model_bounds(objects)
                setup_studio_lighting(center, D)
                setup_hdri_world()
                if props.use_backdrop:
                    setup_cyclorama_backdrop(
                        center, D,
                        color=props.backdrop_color,
                        texture_path=props.backdrop_texture,
                    )

        elif stage == 'render':
            if props.batch_do_render and state.current_import_result and state.current_import_result["success"]:
                scene = bpy.context.scene
                apply_render_preset(scene, 'BATCH')
                out_dir = os.path.join(
                    props.batch_output_dir,
                    os.path.splitext(os.path.basename(filepath))[0],
                )
                os.makedirs(out_dir, exist_ok=True)
                out = get_output_path(
                    os.path.splitext(os.path.basename(filepath))[0],
                    'BATCH', 'front', out_dir,
                )
                scene.render.filepath = out
                bpy.ops.render.render(write_still=True)

        elif stage == 'cleanup':
            elapsed = time.time() - state.model_start_time
            state.results.append({
                "filename": filename,
                "status": "success",
                "error": None,
                "processing_time_seconds": round(elapsed, 2),
                "output_files": [],
            })
            bpy.data.orphans_purge(do_recursive=True)

            state.current_index += 1
            state.current_stage = 0
            return 0.01

    except Exception as exc:
        logger.exception("Batch stage '%s' failed for %s", stage, filepath)
        _skip_model(state, filepath, str(exc))
        return 0.01

    state.current_stage += 1
    return 0.01


def _skip_model(state, filepath, error):
    elapsed = time.time() - state.model_start_time
    state.results.append({
        "filename": os.path.basename(filepath),
        "status": "failed",
        "error": error,
        "processing_time_seconds": round(elapsed, 2),
        "output_files": [],
    })
    state.current_index += 1
    state.current_stage = 0
    try:
        bpy.data.orphans_purge(do_recursive=True)
    except Exception:
        pass


def _finalize_batch(state, props):
    total_time = time.time() - state.start_time
    generate_batch_report(
        state.batch_id,
        props.batch_input_dir,
        props.batch_output_dir,
        state.results,
        total_time,
    )
    props.batch_progress = 100.0
    props.batch_current_file = ""
    bpy.context.workspace.status_text_set(None)
    logger.info("Batch complete: %d/%d succeeded",
                sum(1 for r in state.results if r["status"] == "success"),
                len(state.results))


class AIIMPORT_OT_batch_process(bpy.types.Operator):
    bl_idname = "aiimport.batch_process"
    bl_label = "Batch Process"
    bl_description = "Process all models in the input folder"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.ai_importer
        if not props.batch_input_dir:
            self.report({'ERROR'}, "No input folder specified")
            return {'CANCELLED'}

        files = scan_directory(props.batch_input_dir, props.batch_recursive)
        if not files:
            self.report({'WARNING'}, "No supported files found in folder")
            return {'CANCELLED'}

        state = BatchState.reset()
        state.file_list = files
        state.start_time = time.time()

        if props.batch_output_dir:
            os.makedirs(props.batch_output_dir, exist_ok=True)

        bpy.app.timers.register(_batch_timer, first_interval=0.1)
        self.report({'INFO'}, f"Batch started: {len(files)} files")
        return {'FINISHED'}


class AIIMPORT_OT_batch_cancel(bpy.types.Operator):
    bl_idname = "aiimport.batch_cancel"
    bl_label = "Cancel Batch"
    bl_description = "Stop batch processing after current stage"
    bl_options = {'REGISTER'}

    def execute(self, context):
        BatchState.get().cancelled = True
        self.report({'INFO'}, "Batch cancellation requested")
        return {'FINISHED'}

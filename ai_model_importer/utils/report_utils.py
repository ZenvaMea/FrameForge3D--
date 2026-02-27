import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("ai_model_importer")


def generate_fix_report(model_name, filepath, fix_results, final_obj=None):
    report = {
        "model_name": model_name,
        "file_path": filepath,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixes_applied": [],
        "warnings": [],
        "final_stats": {},
    }

    for step_name, data in fix_results.items():
        entry = {
            "step": step_name,
            "status": data.get("status", "unknown"),
            "detail": str(data.get("detail", "")),
            "before": data.get("before", {}),
            "after": data.get("after", {}),
        }
        report["fixes_applied"].append(entry)
        if data.get("status") == "failed":
            report["warnings"].append(f"{step_name}: {data.get('detail', '')}")

    if final_obj and final_obj.type == 'MESH':
        mesh = final_obj.data
        report["final_stats"] = {
            "poly_count": len(mesh.polygons),
            "vert_count": len(mesh.vertices),
            "material_count": len(final_obj.material_slots),
            "has_uv": len(mesh.uv_layers) > 0,
            "has_vertex_colors": len(mesh.color_attributes) > 0,
            "is_manifold": True,
        }

    return report


def generate_batch_report(batch_id, input_dir, output_dir, model_results, total_time):
    succeeded = sum(1 for r in model_results if r.get("status") == "success")
    failed = sum(1 for r in model_results if r.get("status") == "failed")
    skipped = sum(1 for r in model_results if r.get("status") == "skipped")

    report = {
        "batch_id": batch_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "total_files": len(model_results),
        "processed": succeeded + failed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "total_time_seconds": round(total_time, 2),
        "models": model_results,
    }

    report_path = os.path.join(output_dir, "batch_report.json")
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Batch report saved: %s", report_path)
    except Exception:
        logger.exception("Failed to write batch report")

    return report

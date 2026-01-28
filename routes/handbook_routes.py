import io
import json
import os
import threading
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, render_template, request, send_file, current_app
from models import db, EngineeringHandbook
from utils.storage_helper import get_upload_dir, get_generated_dir, save_uploaded_file, save_text_content
from utils.handbook_agent import HandbookAgent
from utils.export_helper import HandbookExporter


handbook_bp = Blueprint("handbook", __name__)

ALLOWED_SYSTEMS = {"US", "UK", "HK-SG"}


def _parse_target_systems(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


def _normalize_systems(raw_value):
    systems = _parse_target_systems(raw_value)
    normalized = []
    for system in systems:
        if not system:
            continue
        candidate = system.upper()
        if candidate in ALLOWED_SYSTEMS:
            normalized.append(candidate)
    return normalized


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _ensure_materials_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return [value]
    return []


def _cleanup_handbook_files(handbook_id):
    for base_dir in (get_upload_dir(handbook_id), get_generated_dir(handbook_id)):
        try:
            for root, dirs, files in os.walk(base_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(base_dir)
        except Exception:
            pass


def _load_content_map(handbook):
    if not handbook.content_versions:
        return {}
    try:
        parsed = json.loads(handbook.content_versions)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _get_handbook_content(handbook, system_type):
    content_map = _load_content_map(handbook)
    return content_map.get(system_type), content_map.get("_meta", {})


def _generate_handbook_background(app, handbook_id):
    with app.app_context():
        handbook = EngineeringHandbook.query.get(handbook_id)
        if not handbook:
            return

        try:
            handbook.status = "generating"
            db.session.commit()

            agent = HandbookAgent()
            systems = _parse_target_systems(handbook.target_systems)
            content_map = {}
            meta_map = {}

            for system_type in systems:
                result = agent.generate_handbook(
                    project_description=handbook.project_description,
                    system_type=system_type,
                    project_name_cn=handbook.project_name_cn,
                    project_name_en=handbook.project_name_en,
                    author_name=handbook.author_name,
                    version=handbook.version,
                    completion_date=handbook.completion_date,
                    source_code_url=handbook.source_code_url,
                    source_code_file=handbook.source_code_file,
                    process_materials=handbook.process_materials,
                )
                if isinstance(result, dict):
                    content = result.get("content") or ""
                    meta = result.get("meta") or {}
                else:
                    content = result or ""
                    meta = {}
                content_map[system_type] = content
                if meta:
                    meta_map[system_type] = meta

                generated_dir = get_generated_dir(handbook_id)
                filename = f"handbook_{system_type}.md"
                file_path = os.path.join(generated_dir, filename)
                with open(file_path, "w", encoding="utf-8") as handle:
                    handle.write(content or "")

            if meta_map:
                content_map["_meta"] = meta_map

            handbook.content_versions = json.dumps(content_map, ensure_ascii=False)
            handbook.status = "completed"
            handbook.completed_at = datetime.utcnow()
            db.session.commit()
        except Exception as exc:
            handbook.status = "failed"
            handbook.error_message = str(exc)
            db.session.commit()


@handbook_bp.route("/generator")
def handbook_generator():
    return render_template("handbook_generator.html")


@handbook_bp.route("/library")
def handbook_library():
    return render_template("handbook_library.html")


@handbook_bp.route("/library/<int:handbook_id>")
def handbook_detail(handbook_id):
    return render_template("handbook_detail.html", handbook_id=handbook_id)


@handbook_bp.route("/api/handbooks")
def api_list_handbooks():
    handbooks = EngineeringHandbook.query.order_by(EngineeringHandbook.created_at.desc()).all()
    return jsonify([h.to_dict(include_content=False) for h in handbooks])


@handbook_bp.route("/api/handbooks/<int:handbook_id>")
def api_get_handbook(handbook_id):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    return jsonify(handbook.to_dict())


@handbook_bp.route("/api/handbooks/upload", methods=["POST"])
def api_create_handbook():
    if request.is_json:
        data = request.get_json() or {}
        files = {}
    else:
        data = request.form.to_dict()
        files = request.files

    project_name_cn = (data.get("project_name_cn") or "").strip()
    if not project_name_cn:
        return jsonify({"error": "项目中文名不能为空"}), 400

    project_description = (data.get("project_description") or "").strip()
    if not project_description:
        return jsonify({"error": "项目说明不能为空"}), 400

    target_systems = _normalize_systems(data.get("target_systems"))
    if not target_systems:
        return jsonify({"error": "请选择目标申请体系"}), 400

    handbook = EngineeringHandbook(
        project_name_cn=project_name_cn,
        project_name_en=(data.get("project_name_en") or "").strip() or None,
        author_name=(data.get("author_name") or "").strip() or None,
        version=(data.get("version") or "v1.0.0").strip(),
        completion_date=_parse_date(data.get("completion_date")),
        target_systems=json.dumps(target_systems),
        status="pending",
        project_description=project_description,
        source_code_url=(data.get("source_code_url") or "").strip() or None,
        process_materials=json.dumps([]),
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.session.add(handbook)
    db.session.commit()

    description_file = files.get("project_description_file") if files else None
    if description_file:
        handbook.project_description_file = save_uploaded_file(
            description_file, handbook.id, subdir="description"
        )
    elif project_description:
        handbook.project_description_file = save_text_content(
            project_description, handbook.id, subdir="description", filename="description.txt"
        )

    source_code_file = files.get("source_code_file") if files else None
    if source_code_file:
        handbook.source_code_file = save_uploaded_file(
            source_code_file, handbook.id, subdir="source_code"
        )

    code_text = (data.get("source_code_text") or "").strip()
    if code_text and not handbook.source_code_file:
        handbook.source_code_file = save_text_content(
            code_text, handbook.id, subdir="source_code", filename="code.txt"
        )

    materials_paths = []
    if files:
        materials_files = files.getlist("process_materials")
        for material in materials_files:
            path = save_uploaded_file(material, handbook.id, subdir="materials")
            if path:
                materials_paths.append(path)

    materials_text = (data.get("process_materials_text") or "").strip()
    if materials_text:
        path = save_text_content(
            materials_text, handbook.id, subdir="materials", filename="materials.txt"
        )
        if path:
            materials_paths.append(path)

    if materials_paths:
        existing = _ensure_materials_list(handbook.process_materials)
        handbook.process_materials = json.dumps(existing + materials_paths, ensure_ascii=False)

    db.session.commit()

    return jsonify({"message": "已创建工程手册任务", "id": handbook.id})


@handbook_bp.route("/api/handbooks/<int:handbook_id>/generate", methods=["POST"])
def api_generate_handbook(handbook_id):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    if handbook.status == "generating":
        return jsonify({"error": "手册正在生成中"}), 400

    handbook.status = "pending"
    handbook.content_versions = None
    handbook.error_message = None
    handbook.completed_at = None
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=_generate_handbook_background, args=(app, handbook_id))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "已开始生成", "handbook": handbook.to_dict(include_content=False)})


@handbook_bp.route("/api/handbooks/<int:handbook_id>/download/<system_type>")
def api_download_handbook(handbook_id, system_type):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    return _download_handbook(handbook, system_type, "md")


@handbook_bp.route("/api/handbooks/<int:handbook_id>/download/<system_type>/<format>")
def api_download_handbook_format(handbook_id, system_type, format):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    return _download_handbook(handbook, system_type, format)


def _download_handbook(handbook, system_type, format):
    system_type = system_type.upper()
    if system_type not in ALLOWED_SYSTEMS:
        return jsonify({"error": "不支持的体系"}), 400

    content, _ = _get_handbook_content(handbook, system_type)
    if not content:
        return jsonify({"error": "该版本尚未生成"}), 400

    format = (format or "md").lower()
    exporter = HandbookExporter()

    if format == "md":
        output = io.BytesIO(content.encode("utf-8"))
        filename = f"{handbook.project_name_cn}_{system_type}_工程手册.md"
        return send_file(
            output,
            mimetype="text/markdown",
            as_attachment=True,
            download_name=filename,
        )
    title = f"工程手册: {handbook.project_name_cn} ({system_type})"

    if format == "docx":
        doc_bytes = exporter.to_word(content, title=title, system_type=system_type)
        output = io.BytesIO(doc_bytes)
        filename = f"{handbook.project_name_cn}_{system_type}_工程手册.docx"
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )

    return jsonify({"error": "不支持的格式"}), 400


@handbook_bp.route("/api/handbooks/<int:handbook_id>/favorite", methods=["POST"])
def api_toggle_favorite(handbook_id):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    handbook.is_favorited = not handbook.is_favorited
    if handbook.is_favorited:
        handbook.expires_at = None
    else:
        handbook.expires_at = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    return jsonify({"message": "已收藏" if handbook.is_favorited else "已取消收藏"})


@handbook_bp.route("/api/handbooks/<int:handbook_id>", methods=["DELETE"])
def api_delete_handbook(handbook_id):
    handbook = EngineeringHandbook.query.get_or_404(handbook_id)
    db.session.delete(handbook)
    db.session.commit()

    _cleanup_handbook_files(handbook_id)
    return jsonify({"message": "已删除"})

"""Enrollment-level feedback share links and PDF export services."""
import html
import io
import secrets
from datetime import timedelta

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import FeedbackShareLink
from modules.oa.models import CourseFeedback, CourseSchedule


def _safe_text(value):
    return str(value or '').strip()


def _feedback_display_rows(item):
    return [
        ('课程内容', _safe_text(item.get('summary'))),
        ('学生表现', _safe_text(item.get('student_performance'))),
        ('课后作业', _safe_text(item.get('homework'))),
        ('下次重点', _safe_text(item.get('next_focus'))),
    ]


def build_enrollment_feedback_report_data(enrollment):
    schedules = CourseSchedule.query.filter_by(
        enrollment_id=enrollment.id,
        is_cancelled=False,
    ).order_by(CourseSchedule.date.asc(), CourseSchedule.time_start.asc(), CourseSchedule.id.asc()).all()

    feedback_items = []
    for schedule in schedules:
        feedback = getattr(schedule, 'feedback', None)
        if not feedback or feedback.status != 'submitted':
            continue
        feedback_items.append({
            'schedule_id': schedule.id,
            'date': schedule.date.isoformat() if schedule.date else None,
            'time_start': schedule.time_start,
            'time_end': schedule.time_end,
            'teacher_name': schedule.teacher,
            'course_name': schedule.course_name,
            'submitted_at': feedback.submitted_at.isoformat() if feedback.submitted_at else None,
            'summary': feedback.summary,
            'student_performance': feedback.student_performance,
            'homework': feedback.homework,
            'next_focus': feedback.next_focus,
        })

    return {
        'enrollment_id': enrollment.id,
        'student_name': enrollment.student_name,
        'course_name': enrollment.course_name,
        'teacher_name': enrollment.teacher.display_name if enrollment.teacher else None,
        'delivery_preference': enrollment.delivery_preference,
        'generated_at': auth_services.get_business_now().isoformat(),
        'feedback_items': feedback_items,
        'total_feedback_count': len(feedback_items),
    }


def create_or_refresh_feedback_share_link(enrollment, *, created_by=None):
    ttl_days = int(current_app.config.get('FEEDBACK_SHARE_LINK_TTL_DAYS') or 30)
    link = FeedbackShareLink.query.filter(
        FeedbackShareLink.enrollment_id == enrollment.id,
        FeedbackShareLink.revoked_at.is_(None),
    ).order_by(FeedbackShareLink.created_at.desc(), FeedbackShareLink.id.desc()).first()
    if not link:
        link = FeedbackShareLink(enrollment_id=enrollment.id)
        db.session.add(link)

    link.token = secrets.token_urlsafe(24)
    link.expires_at = auth_services.get_business_now() + timedelta(days=max(ttl_days, 1))
    link.revoked_at = None
    link.created_by = getattr(created_by, 'id', None)
    link.last_accessed_at = None
    db.session.commit()
    return link


def revoke_feedback_share_links(enrollment):
    now = auth_services.get_business_now()
    FeedbackShareLink.query.filter(
        FeedbackShareLink.enrollment_id == enrollment.id,
        FeedbackShareLink.revoked_at.is_(None),
    ).update({'revoked_at': now}, synchronize_session=False)
    db.session.commit()


def resolve_feedback_share_link(token):
    link = FeedbackShareLink.query.filter_by(token=str(token or '').strip()).first()
    if not link:
        return None, '分享链接不存在'
    now = auth_services.get_business_now()
    if link.revoked_at:
        return None, '分享链接已失效'
    if link.expires_at and link.expires_at < now:
        return None, '分享链接已过期'

    link.last_accessed_at = now
    db.session.commit()
    return link, None


def _pdf_styles():
    if 'STSong-Light' not in pdfmetrics.getRegisteredFontNames():
        registerFont(UnicodeCIDFont('STSong-Light'))
    styles = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'FeedbackTitle',
            parent=styles['Title'],
            fontName='STSong-Light',
            fontSize=18,
            leading=24,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=12,
        ),
        'heading': ParagraphStyle(
            'FeedbackHeading',
            parent=styles['Heading2'],
            fontName='STSong-Light',
            fontSize=13,
            leading=18,
            textColor=colors.HexColor('#0369a1'),
            spaceAfter=8,
        ),
        'body': ParagraphStyle(
            'FeedbackBody',
            parent=styles['BodyText'],
            fontName='STSong-Light',
            fontSize=10,
            leading=16,
            textColor=colors.HexColor('#0f172a'),
        ),
        'meta': ParagraphStyle(
            'FeedbackMeta',
            parent=styles['BodyText'],
            fontName='STSong-Light',
            fontSize=9,
            leading=14,
            textColor=colors.HexColor('#475569'),
        ),
    }


def render_feedback_report_pdf(report_data):
    styles = _pdf_styles()
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=36,
    )
    elements = [
        Paragraph('SCF 课程反馈报告', styles['title']),
        Paragraph(
            html.escape(
                f"学生：{report_data.get('student_name') or '-'}　课程：{report_data.get('course_name') or '-'}　老师：{report_data.get('teacher_name') or '-'}"
            ),
            styles['meta'],
        ),
        Spacer(1, 14),
    ]

    for index, item in enumerate(report_data.get('feedback_items') or [], 1):
        title = f"第 {index} 次反馈 | {item.get('date') or '-'} {item.get('time_start') or ''}-{item.get('time_end') or ''}"
        elements.append(Paragraph(html.escape(title), styles['heading']))
        meta_lines = [
            f"授课老师：{item.get('teacher_name') or '-'}",
            f"提交时间：{item.get('submitted_at') or '-'}",
        ]
        elements.append(Paragraph(html.escape('　'.join(meta_lines)), styles['meta']))

        rows = [[Paragraph('<b>字段</b>', styles['body']), Paragraph('<b>内容</b>', styles['body'])]]
        for label, value in _feedback_display_rows(item):
            rows.append([
                Paragraph(html.escape(label), styles['body']),
                Paragraph(html.escape(value or '-').replace('\n', '<br/>'), styles['body']),
            ])
        table = Table(rows, colWidths=[72, 410])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0f2fe')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0f172a')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.extend([Spacer(1, 6), table, Spacer(1, 14)])

    if not report_data.get('feedback_items'):
        elements.append(Paragraph('当前暂无已提交的课程反馈。', styles['body']))

    document.build(elements)
    output.seek(0)
    filename = f"{report_data.get('student_name') or 'student'}_{report_data.get('course_name') or 'course'}_课程反馈报告.pdf"
    return output, filename

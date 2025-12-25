import os
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Dict, Any

class ReportGenerator:
    """
    负责将分析结果转换为标准 Word 文档
    """
    
    @staticmethod
    def generate_docx(analysis_data: Dict[str, Any], output_path: str = "report.docx") -> str:
        """
        输入: LLM 分析生成的 JSON (完整结构)
        输出: 生成文件的路径
        """
        doc = Document()
        
        # 1. 标题 (EFund 风格)
        heading = doc.add_heading('易方达基金 - 政策分析解读报告', 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 副标题：政策名称
        # [防御性] 使用 .get 并且提供默认值，防止 NoneType 报错
        policy_info = analysis_data.get('selected_policy', {}) or {}
        policy_title = policy_info.get('title', '未命名政策')
        
        subtitle = doc.add_paragraph(policy_title)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.runs[0].bold = True
        
        # 来源信息
        meta_para = doc.add_paragraph()
        meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta_para.add_run(f"发布机构: {policy_info.get('issuer', '-')}\t").italic = True
        meta_para.add_run(f"发布时间: {policy_info.get('publish_date', '-')}\t").italic = True
        
        doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 2. 正文内容生成
        content_data = analysis_data.get('docx_content', {}) or {}
        
        # 定义需要输出的章节顺序
        sections = [
            ("摘要", content_data.get("摘要", [])),
            ("政策要点与变化", content_data.get("政策要点与变化", [])),
            ("对指数与行业的影响", content_data.get("对指数与行业的影响", [])),
            ("对指数基金管理人的投资建议", content_data.get("对指数基金管理人的投资建议", [])),
            ("EFund 战略与行动建议", content_data.get("EFund_战略与行动建议", []))
        ]
        
        for section_title, bullets in sections:
            if not bullets: continue
            
            # 章节标题
            h = doc.add_heading(section_title, level=1)
            
            # 章节内容 (Bullet Points)
            if isinstance(bullets, list):
                for point in bullets:
                    # [防御性] 确保 point 是字符串
                    if isinstance(point, str):
                        doc.add_paragraph(point, style='List Bullet')
                    else:
                        doc.add_paragraph(str(point), style='List Bullet')
            else:
                doc.add_paragraph(str(bullets))
                
        # 3. 引用来源区块 (合规必备)
        doc.add_heading('引用与依据', level=1)
        quotes = content_data.get("引用区块", [])
        
        if isinstance(quotes, list):
            for q in quotes:
                # [关键修复] 检查 q 的类型
                if isinstance(q, dict):
                    # 情况 A: LLM 乖乖输出了字典 (标准情况)
                    p = doc.add_paragraph()
                    p.add_run(f"结论: {q.get('claim', '-')}\n").bold = True
                    p.add_run(f"原文依据: {q.get('evidence', '-')}\n").italic = True
                    p.add_run(f"来源链接: {q.get('source_url', '-')}")
                elif isinstance(q, str):
                    # 情况 B: LLM 偷懒输出了字符串 (你的报错情况)
                    # 直接把字符串打印出来，不至于报错
                    doc.add_paragraph(q)
                else:
                    continue

        # 4. 底部免责声明
        doc.add_page_break()
        footer = doc.add_paragraph("本报告仅供易方达内部投研参考，不构成公开投资建议。")
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in footer.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(128, 128, 128)

        # 保存
        try:
            doc.save(output_path)
        except PermissionError:
            # 防止文件被打开时无法写入
            doc.save(f"report_{os.urandom(2).hex()}.docx")
            
        return output_path
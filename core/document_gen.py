import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from typing import Dict, Any

class ReportGenerator:
    """
    负责将分析结果转换为标准 Word 文档
    应用易方达品牌格式标准
    """
    
    @staticmethod
    def set_efund_style(doc):
        """设置易方达品牌样式"""
        # 设置默认字体
        doc.styles['Normal'].font.name = '宋体'
        doc.styles['Normal'].font.size = Pt(10.5)  # 五号 = 10.5pt
        doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        
        # 设置英文字体
        doc.styles['Normal'].font.name = 'Times New Roman'
        
        # 段落格式
        doc.styles['Normal'].paragraph_format.line_spacing = Pt(18)
        doc.styles['Normal'].paragraph_format.space_before = Pt(6)  # 0.5行约6pt
        doc.styles['Normal'].paragraph_format.space_after = Pt(6)
        doc.styles['Normal'].paragraph_format.first_line_indent = Inches(0.25)  # 首行缩进2字符
        doc.styles['Normal'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY  # 两端对齐

    @staticmethod
    def add_efund_heading(doc, text, level=1):
        """添加易方达风格的标题"""
        heading = doc.add_heading(text, level=level)
        
        # 设置标题颜色为易方达蓝
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0, 78, 157)
            
            if level == 1:
                run.font.name = '黑体'
                run.font.size = Pt(14)  # 4号 = 14pt
                run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            elif level == 2:
                run.font.name = '黑体'
                run.font.size = Pt(12)  # 小四 = 12pt
                run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(6)
        
        return heading
    
    @staticmethod
    def generate_docx(analysis_data: Dict[str, Any], output_path: str = "report.docx") -> str:
        """
        输入: LLM 分析生成的 JSON (完整结构)
        输出: 生成文件的路径
        """
        doc = Document()
        
        # 应用易方达样式
        ReportGenerator.set_efund_style(doc)
        
        # 1. 标题
        heading = doc.add_heading('易方达基金 - 政策分析解读报告', 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0, 78, 157)
        
        # 2. 政策信息
        policy_info = analysis_data.get('selected_policy', {}) or {}
        policy_title = policy_info.get('title', '未命名政策')
        
        subtitle = doc.add_paragraph(policy_title)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.runs[0].bold = True
        subtitle.runs[0].font.size = Pt(16)
        subtitle.paragraph_format.first_line_indent = Inches(0)
        
        # 元信息
        meta_para = doc.add_paragraph()
        meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta_para.paragraph_format.first_line_indent = Inches(0)
        meta_run1 = meta_para.add_run(f"发布机构: {policy_info.get('issuer', '-')}  ")
        meta_run1.italic = True
        meta_run1.font.size = Pt(10.5)
        meta_run2 = meta_para.add_run(f"发布时间: {policy_info.get('publish_date', '-')}  ")
        meta_run2.italic = True
        meta_run2.font.size = Pt(10.5)
        meta_run3 = meta_para.add_run(f"来源: {policy_info.get('url', '-')}")
        meta_run3.italic = True
        meta_run3.font.size = Pt(10.5)
        meta_run3.font.color.rgb = RGBColor(0, 78, 157)  # 易方达蓝色链接
        
        doc.add_paragraph()  # 空行

        
        # 3. 正文内容
        content_data = analysis_data.get('docx_content', {}) or {}
        
        # 定义章节
        sections = [
            ("摘要", content_data.get("摘要", [])),
            ("政策要点与变化", content_data.get("政策要点与变化", [])),
            ("对指数及其行业的影响", content_data.get("对指数及其行业的影响", [])),
            ("对指数基金管理公司的建议", content_data.get("对指数基金管理公司的建议", [])),
            ("对易方达的战略行动建议", content_data.get("对易方达的战略行动建议", []))
        ]
        
        for section_title, paragraphs in sections:
            if not paragraphs:
                continue
            
            # 添加易方达风格标题
            ReportGenerator.add_efund_heading(doc, section_title, level=1)
            
            # 添加段落内容
            if isinstance(paragraphs, list):
                for para_text in paragraphs:
                    if isinstance(para_text, str) and para_text.strip():
                        p = doc.add_paragraph(para_text)
                        # 应用正文格式
                        p.paragraph_format.first_line_indent = Inches(0.25)
                        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                        p.paragraph_format.line_spacing = Pt(18)
                        p.paragraph_format.space_before = Pt(6)
                        p.paragraph_format.space_after = Pt(6)
            else:
                p = doc.add_paragraph(str(paragraphs))
                p.paragraph_format.first_line_indent = Inches(0.25)
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        
        
        # 4. 免责声明
        doc.add_page_break()

        footer = doc.add_paragraph("本报告仅供易方达内部投研参考，不构成公开投资建议。")
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer.paragraph_format.first_line_indent = Inches(0)
        for run in footer.runs:
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(128, 128, 128)
        
        # 保存
        try:
            doc.save(output_path)
        except PermissionError:
            output_path = f"report_{os.urandom(2).hex()}.docx"
            doc.save(output_path)
        
        return output_path
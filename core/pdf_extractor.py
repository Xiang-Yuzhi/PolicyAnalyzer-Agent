"""
PDF Extractor: 从网页中提取并解析 PDF 文件

功能：
1. 从网页内容中提取 PDF 下载链接
2. 下载 PDF 文件并提取全文内容
3. 支持嵌入式 PDF (embed/iframe) 和直接链接
"""

import re
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

# PDF 解析
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("⚠️ PyMuPDF 未安装，将无法解析 PDF 内容")

# HTML 解析
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("⚠️ BeautifulSoup 未安装，将无法提取 PDF 链接")


class PDFExtractor:
    """PDF 提取与解析器"""
    
    # 常见的政策 PDF 文件名模式
    PDF_PATTERNS = [
        r'\.pdf$',
        r'\.PDF$',
        r'/download/',
        r'/attachment/',
        r'/file/',
    ]
    
    # 请求头模拟浏览器
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    @staticmethod
    def extract_pdf_links(page_url: str, html_content: Optional[str] = None) -> List[Dict[str, str]]:
        """
        从网页中提取 PDF 下载链接
        
        Returns:
            [{"url": "完整PDF链接", "title": "链接文本或文件名"}]
        """
        if not HAS_BS4:
            return []
        
        pdf_links = []
        
        try:
            if not html_content:
                response = requests.get(page_url, headers=PDFExtractor.HEADERS, timeout=15, verify=False)
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 方式1: 直接的 <a href="xxx.pdf"> 链接
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if re.search(r'\.pdf', href, re.I):
                    full_url = urljoin(page_url, href)
                    title = a.get_text(strip=True) or PDFExtractor._extract_filename(full_url)
                    pdf_links.append({"url": full_url, "title": title})
            
            # 方式2: 嵌入的 <embed> 或 <iframe> 标签
            for tag in soup.find_all(['embed', 'iframe', 'object']):
                src = tag.get('src') or tag.get('data', '')
                if src and '.pdf' in src.lower():
                    full_url = urljoin(page_url, src)
                    pdf_links.append({"url": full_url, "title": "嵌入式PDF文档"})
            
            # 方式3: JavaScript 动态加载的链接 (简单模式匹配)
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.string or ''
                pdf_matches = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', script_text, re.I)
                for match in pdf_matches:
                    if match.startswith('http'):
                        pdf_links.append({"url": match, "title": PDFExtractor._extract_filename(match)})
                    elif match.startswith('/'):
                        full_url = urljoin(page_url, match)
                        pdf_links.append({"url": full_url, "title": PDFExtractor._extract_filename(full_url)})
            
            # 去重
            seen = set()
            unique_links = []
            for link in pdf_links:
                if link['url'] not in seen:
                    seen.add(link['url'])
                    unique_links.append(link)
            
            return unique_links
            
        except Exception as e:
            print(f"❌ 提取 PDF 链接失败: {e}")
            return []
    
    @staticmethod
    def download_and_parse_pdf(pdf_url: str, max_pages: int = 10) -> Tuple[str, Optional[str]]:
        """
        下载 PDF 并提取全文内容 (限制前10页以平衡性能与资源)
        
        Returns:
            (提取 of 的文本内容, 错误信息或None)
        """
        if not HAS_PYMUPDF:
            return "", "PyMuPDF 未安装"
        
        try:
            print(f"📥 正在下载 PDF: {pdf_url[:80]}...")
            # 增加超时保护
            response = requests.get(pdf_url, headers=PDFExtractor.HEADERS, timeout=20, verify=False)
            response.raise_for_status()
            
            # 检查文件大小 (如超过 15MB 则跳过下载，避免内存崩溃)
            file_size = len(response.content)
            if file_size > 15 * 1024 * 1024:
                return "", f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，跳过深度下载以节省资源"
            
            # 使用 PyMuPDF 解析
            doc = fitz.open(stream=response.content, filetype="pdf")
            
            text_parts = []
            # 限制页数，政策文件核心通常在前10页
            page_count = min(len(doc), max_pages)
            
            for page_num in range(page_count):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{page_text}")
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            # 限制总字符，避免 token 爆炸
            full_text = full_text[:30000]
            
            print(f"✅ PDF 解析完成: {len(full_text)} 字符, {page_count} 页")
            
            return full_text, None
            
        except requests.exceptions.RequestException as e:
            return "", f"下载失败: {e}"
        except Exception as e:
            return "", f"解析失败: {e}"
    
    @staticmethod
    def extract_and_parse(page_url: str, html_content: Optional[str] = None) -> Dict[str, any]:
        """
        一站式提取：从网页提取 PDF 链接并解析内容
        
        Returns:
            {
                "pdf_links": [{"url": "...", "title": "..."}],
                "pdf_content": "解析出的PDF全文",
                "source_pdf_url": "内容来源的PDF链接",
                "error": "错误信息或None"
            }
        """
        result = {
            "pdf_links": [],
            "pdf_content": "",
            "source_pdf_url": None,
            "error": None
        }
        
        # 1. 提取所有 PDF 链接
        pdf_links = PDFExtractor.extract_pdf_links(page_url, html_content)
        result["pdf_links"] = pdf_links
        
        if not pdf_links:
            result["error"] = "未在网页中发现 PDF 文件"
            return result
        
        # 2. 尝试解析第一个 PDF (通常是正文)
        for link in pdf_links:
            content, error = PDFExtractor.download_and_parse_pdf(link["url"])
            if content and len(content) > 500:  # 有实质内容
                result["pdf_content"] = content
                result["source_pdf_url"] = link["url"]
                break
            elif error:
                result["error"] = error
        
        return result
    
    @staticmethod
    def _extract_filename(url: str) -> str:
        """从 URL 中提取文件名"""
        parsed = urlparse(url)
        path = parsed.path
        filename = path.split('/')[-1] if '/' in path else path
        return filename or "未知文件"


# 单例实例
pdf_extractor = PDFExtractor()


# 测试代码
if __name__ == "__main__":
    test_url = "https://www.csrc.gov.cn/csrc/c100028/c7443184/content.shtml"
    
    print("=== 测试 PDF 提取 ===")
    result = pdf_extractor.extract_and_parse(test_url)
    
    print(f"\n找到 PDF 链接: {len(result['pdf_links'])}")
    for link in result['pdf_links']:
        print(f"  - {link['title']}: {link['url'][:60]}...")
    
    if result['pdf_content']:
        print(f"\nPDF 内容预览 (前500字):\n{result['pdf_content'][:500]}")
    else:
        print(f"\n错误: {result['error']}")

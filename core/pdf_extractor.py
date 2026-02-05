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
        从网页中提取 PDF 下载链接（优化证监会等政府网站）
        
        Returns:
            [{"url": "完整PDF链接", "title": "链接文本或文件名"}]
        """
        if not HAS_BS4:
            return []
        
        pdf_links = []
        
        try:
            if not html_content:
                response = requests.get(page_url, headers=PDFExtractor.HEADERS, timeout=15, verify=False)
                response.encoding = response.apparent_encoding  # 修复编码问题
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 解析基础 URL（用于正确拼接相对路径）
            parsed_base = urlparse(page_url)
            base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
            # 获取当前页面所在目录（用于处理相对路径）
            page_dir = page_url.rsplit('/', 1)[0] if '/' in parsed_base.path else page_url
            
            print(f"🔍 正在分析页面: {page_url}")
            print(f"   基础URL: {base_url}, 页面目录: {page_dir}")
            
            # 优先方式: 从 #files 或 class=files 容器中提取 (证监会网站特有结构)
            files_containers = soup.find_all(['div', 'section'], id='files') or \
                               soup.find_all(['div', 'section'], class_='files') or \
                               soup.find_all(['div'], id=re.compile(r'file', re.I))
            
            if files_containers:
                print(f"   ✅ 找到 {len(files_containers)} 个文件容器")
                for container in files_containers:
                    for a in container.find_all('a', href=True):
                        href = a.get('href', '')
                        if re.search(r'\.pdf', href, re.I):
                            # 智能拼接完整 URL
                            full_url = PDFExtractor._build_full_url(href, page_url, base_url, page_dir)
                            title = a.get_text(strip=True) or PDFExtractor._extract_filename(full_url)
                            pdf_links.append({"url": full_url, "title": title, "source": "files_container"})
                            print(f"   📎 [容器] {title[:40]} -> {full_url}")
            
            # 备用方式: 全局搜索 <a href="xxx.pdf">
            if not pdf_links:
                print(f"   ⚠️ 未在 files 容器中找到 PDF，尝试全局搜索")
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    if re.search(r'\.pdf', href, re.I):
                        full_url = PDFExtractor._build_full_url(href, page_url, base_url, page_dir)
                        title = a.get_text(strip=True) or PDFExtractor._extract_filename(full_url)
                        pdf_links.append({"url": full_url, "title": title, "source": "global_search"})
                        print(f"   📎 [全局] {title[:40]} -> {full_url}")
            
            # 去重
            seen = set()
            unique_links = []
            for link in pdf_links:
                if link['url'] not in seen:
                    seen.add(link['url'])
                    unique_links.append(link)
            
            print(f"   📊 共找到 {len(unique_links)} 个唯一 PDF 链接")
            return unique_links
            
        except Exception as e:
            print(f"❌ 提取 PDF 链接失败: {e}")
            return []
    
    @staticmethod
    def _build_full_url(href: str, page_url: str, base_url: str, page_dir: str) -> str:
        """智能拼接完整 URL"""
        href = href.strip()
        
        # 已经是完整 URL
        if href.startswith('http://') or href.startswith('https://'):
            return href
        
        # 绝对路径 (以 / 开头)
        if href.startswith('/'):
            return base_url + href
        
        # 相对路径 (不以 / 开头)
        # 使用页面所在目录拼接
        return page_dir + '/' + href
    
    @staticmethod
    def download_and_parse_pdf(pdf_url: str, max_pages: int = 15) -> Tuple[str, Optional[str]]:
        """
        下载 PDF 并提取全文内容
        
        Returns:
            (提取的文本内容, 错误信息或None)
        """
        if not HAS_PYMUPDF:
            return "", "PyMuPDF 未安装"
        
        try:
            print(f"📥 正在下载 PDF: {pdf_url}")
            
            # 增加重定向跟踪，使用 Session 保持 cookies
            session = requests.Session()
            response = session.get(
                pdf_url, 
                headers=PDFExtractor.HEADERS, 
                timeout=30, 
                verify=False,
                allow_redirects=True
            )
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', 'unknown')
            final_url = response.url  # 跟踪重定向后的最终 URL
            file_size = len(response.content)
            
            print(f"  📊 响应信息: 状态码={response.status_code}, 内容类型={content_type}, 大小={file_size/1024:.1f}KB")
            print(f"  🔗 最终URL: {final_url}")
            
            # 检查是否被重定向到非 PDF 页面
            if final_url != pdf_url:
                print(f"  ⚠️ 发生重定向: {pdf_url} -> {final_url}")
            
            # 检查文件大小
            if file_size > 15 * 1024 * 1024:
                return "", f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，跳过下载"
            
            if file_size < 100:
                return "", f"文件过小 ({file_size} 字节)，可能不是有效 PDF"
            
            # 核心修复：检查内容是否为有效 PDF (魔数验证)
            pdf_content = response.content
            if not pdf_content.startswith(b'%PDF'):
                # 检查是否是 HTML 错误页
                if b'<html' in pdf_content[:500].lower() or b'<!doctype' in pdf_content[:500].lower():
                    error_preview = pdf_content[:200].decode('utf-8', errors='ignore')
                    print(f"  ❌ 服务器返回 HTML 而非 PDF: {error_preview[:100]}...")
                    return "", "服务器返回 HTML 页面而非 PDF 文件（可能需要登录或链接已失效）"
                else:
                    print(f"  ❌ 内容不是有效 PDF，前20字节: {pdf_content[:20]}")
                    return "", "下载的内容不是有效的 PDF 文件"
            
            print(f"  ✅ PDF 魔数验证通过，开始解析...")
            
            # 使用 PyMuPDF 解析
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            
            text_parts = []
            page_count = min(len(doc), max_pages)
            
            for page_num in range(page_count):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{page_text}")
            
            total_pages = len(doc)
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            full_text = full_text[:30000]  # 限制总字符
            
            print(f"  ✅ PDF 解析成功: {len(full_text)} 字符, 解析 {page_count}/{total_pages} 页")
            
            return full_text, None
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 下载失败: {e}")
            return "", f"下载失败: {e}"
        except Exception as e:
            print(f"  ❌ 解析失败: {e}")
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
        print(f"🔍 在页面中发现 {len(pdf_links)} 个可能的 PDF 链接")
        
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

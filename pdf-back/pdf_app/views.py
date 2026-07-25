from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.http import FileResponse, HttpResponse
import PyPDF2
import tempfile
import os
import io
import zipfile
import fitz
import magic
import yara

fitz.TOOLS.fitz_config["disable_js"] = True
from .models import PdfTask

# 全局安全配置
MAX_PDF_SIZE = 50 * 1024 * 1024  # 单文件最大50MB
TEMP_DIR = tempfile.gettempdir()  # 统一临时目录
# YARA规则文件路径
YARA_RULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../pdf_rules.yar")

# 预编译YARA规则（全局只编译一次）
try:
    yara_rule = yara.compile(filepath=YARA_RULE_PATH)
except Exception as e:
    print(f"YARA规则加载失败: {e}")
    yara_rule = None

class PdfBaseView(APIView):
    """公共基类，抽取所有PDF通用逻辑，统一安全校验"""
    parser_classes = [MultiPartParser]

    def clean_temp(self, path):
        """安全清理临时文件"""
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    def sanitize_pdf_writer(self, writer: PyPDF2.PdfWriter):
        """清除PDF内嵌JS、自动打开动作，输出干净无恶意脚本PDF"""
        # 删除自动执行、页面动作、附件相关字段
        if hasattr(writer, "_root_object"):
            root = writer._root_object
            root.pop("/OpenAction", None)
            root.pop("/AA", None)
            root.pop("/JavaScript", None)
            root.pop("/Names", None)

    def load_pdf_reader(self, file_obj, password=""):
        """
        读取PDF、解密、前置安全校验，返回reader、总页数、临时文件路径
        """
        # 安全校验1：文件大小限制
        if file_obj.size > MAX_PDF_SIZE:
            raise Exception(f"PDF文件过大，最大支持{MAX_PDF_SIZE // 1024 // 1024}MB")

        # 安全校验2：校验PDF文件头，拦截伪装文件
        header = file_obj.read(5)
        file_obj.seek(0)
        if not header.startswith(b"%PDF-"):
            raise Exception("文件不是合法PDF，禁止上传")

        # 写入临时文件
        temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=TEMP_DIR)
        temp_in.write(file_obj.read())
        temp_in.close()
        input_path = temp_in.name

        reader = PyPDF2.PdfReader(input_path)
        if reader.is_encrypted:
            if not password:
                raise Exception("PDF已加密，请输入打开密码")
            if not reader.decrypt(password):
                raise Exception("密码错误，解密失败")

        return reader, len(reader.pages), input_path


# ====================== 【修改后】PDF安全扫描视图 ======================
class PdfSecurityScanView(PdfBaseView):
    """
    PDF安全检测：静态特征风险检测 + YARA规则检测高危PDF
    返回统一风险判断，前端接口完全兼容不变
    """
    def pdf_static_scan_buffer(self, pdf_bytes: bytes):
        """静态二进制特征检索，替代pdfid，无额外依赖"""
        risk_mapping = {
            b"/JavaScript": "包含JavaScript脚本",
            b"/JS": "包含JS脚本",
            b"/OpenAction": "存在自动打开动作",
            b"/AA": "存在附加自动动作",
            b"/RichMedia": "包含富媒体对象",
            b"/EmbeddedFile": "内嵌附件文件",
            b"/Launch": "存在启动外部程序指令",
            b"/URI": "包含外部链接动作"
        }
        found = set()
        data_low = pdf_bytes.lower()
        for raw, desc in risk_mapping.items():
            if raw.lower() in data_low:
                found.add(desc)
        if found:
            return False, f"检测到元素：{','.join(found)}"
        return True, ""

    def yara_scan_buffer(self, buffer_bytes):
        """YARA二进制匹配高危PDF标记"""
        if not yara_rule:
            return False, "YARA规则加载失败，无法检测脚本风险"
        matches = yara_rule.match(data=buffer_bytes)
        if matches:
            risk_desc = ",".join([m.rule for m in matches])
            return False, f"YARA检测到高危PDF结构: {risk_desc}"
        return True, ""

    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        password = request.data.get("password", "")
        if not pdf_file:
            return Response({"code": 400, "msg": "请上传PDF文件"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        try:
            # 基础校验 + 落地临时文件
            reader, total, input_path = self.load_pdf_reader(pdf_file, password)
            pdf_file.seek(0)
            file_buffer = pdf_file.read()
            pdf_file.seek(0)

            # 第一层：静态特征扫描
            static_ok, static_msg = self.pdf_static_scan_buffer(file_buffer)
            if not static_ok:
                return Response({
                    "code": 200,
                    "safe": False,
                    "msg": static_msg
                })

            # 第二层：YARA规则检测
            yara_ok, yara_msg = self.yara_scan_buffer(file_buffer)
            if not yara_ok:
                return Response({
                    "code": 200,
                    "safe": False,
                    "msg": yara_msg
                })

            self.clean_temp(input_path)
            return Response({
                "code": 200,
                "safe": True,
                "msg": "静态特征检测与YARA双重检测通过，文档无安全风险"
            })

        except Exception as err:
            self.clean_temp(input_path)
            return Response({"code": 400, "msg": f"检测失败: {str(err)}"}, status=status.HTTP_400_BAD_REQUEST)

# ========== 下面其余视图代码完全不变，直接保留 ==========
class SplitPdfView(PdfBaseView):
    """指定起止页拆分PDF，输出单个干净PDF"""
    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        page1 = request.data.get("page1")
        page2 = request.data.get("page2")
        password = request.data.get("password", "")

        if not pdf_file or page1 is None or page2 is None:
            return Response({"code": 400, "msg": "缺少PDF文件或页码参数"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            page1 = int(page1)
            page2 = int(page2)
        except ValueError:
            return Response({"code": 400, "msg": "页码必须是数字"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        output_path = ""
        try:
            reader, total, input_path = self.load_pdf_reader(pdf_file, password)

            s_idx = page1 - 1
            e_idx = page2 - 1
            if not (0 <= s_idx < total and 0 <= e_idx < total and s_idx <= e_idx):
                raise Exception(f"页码超出范围，当前PDF共{total}页")

            writer = PyPDF2.PdfWriter()
            for i in range(s_idx, e_idx + 1):
                writer.add_page(reader.pages[i])
            self.sanitize_pdf_writer(writer)

            temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=TEMP_DIR)
            writer.write(temp_out)
            temp_out.close()
            output_path = temp_out.name

            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=page1,
                end_page=page2,
                status="success"
            )
            self.clean_temp(input_path)

            resp = FileResponse(open(output_path, "rb"),
                                filename=f"{pdf_file.name.replace('.pdf', '')}_{page1}-{page2}.pdf")
            # 响应回调兜底清理
            resp.background = lambda p=output_path: self.clean_temp(p)
            return resp

        except Exception as err:
            self.clean_temp(input_path)
            self.clean_temp(output_path)
            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "unknown.pdf",
                start_page=page1,
                end_page=page2,
                status=f"失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class SplitAllPageZipView(PdfBaseView):
    """全部页面单独PDF打包ZIP返回，内存生成zip减少磁盘落地"""
    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        password = request.data.get("password", "")

        if not pdf_file:
            return Response({"code": 400, "msg": "缺少PDF文件"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        try:
            reader, total, input_path = self.load_pdf_reader(pdf_file, password)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for page_num in range(1, total + 1):
                    idx = page_num - 1
                    writer = PyPDF2.PdfWriter()
                    writer.add_page(reader.pages[idx])
                    self.sanitize_pdf_writer(writer)

                    page_buf = io.BytesIO()
                    writer.write(page_buf)
                    page_buf.seek(0)
                    zf.writestr(f"{page_num}.pdf", page_buf.getvalue())

            zip_buffer.seek(0)
            self.clean_temp(input_path)

            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=1,
                end_page=total,
                status="success"
            )

            origin_name = pdf_file.name.replace(".pdf", "")
            resp = HttpResponse(zip_buffer, content_type="application/zip")
            resp["Content-Disposition"] = f'attachment; filename="{origin_name}_all.zip"'
            return resp

        except Exception as err:
            self.clean_temp(input_path)
            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "未知文件",
                start_page=1,
                end_page=0,
                status=f"失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class MergeAllView(PdfBaseView):
    """多PDF截取指定页面后合并为单个PDF"""
    def post(self, request):
        pdf_files = request.FILES.getlist("pdf_files")
        start_list = request.POST.getlist("starts")
        end_list = request.POST.getlist("ends")
        pwd_list = request.POST.getlist("passwords")

        if len(pdf_files) == 0:
            return Response({"code": 400, "msg": "请至少上传一个PDF文件"}, status=status.HTTP_400_BAD_REQUEST)
        if not (len(pdf_files) == len(start_list) == len(end_list)):
            return Response({"code": 400, "msg": "文件数量与页码数组数量不匹配"}, status=status.HTTP_400_BAD_REQUEST)

        input_paths = []
        output_temp_path = ""
        total_all_pages = 0
        file_names = []

        try:
            writer = PyPDF2.PdfWriter()

            for idx in range(len(pdf_files)):
                f = pdf_files[idx]
                s_str = start_list[idx]
                e_str = end_list[idx]
                raw_pwd = pwd_list[idx] if idx < len(pwd_list) else ""
                pwd = str(raw_pwd).strip() if raw_pwd is not None else ""
                file_names.append(f.name)

                try:
                    page_start = int(s_str) - 1
                    page_end = int(e_str)
                except ValueError:
                    raise Exception(f"第{idx + 1}个PDF页码必须为数字")

                reader, total, temp_in_path = self.load_pdf_reader(f, pwd)
                input_paths.append(temp_in_path)

                if not (0 <= page_start < total and page_end <= total and page_start < page_end):
                    raise Exception(f"【{f.name}】页码越界，文档总页数{total}")

                for i in range(page_start, page_end):
                    writer.add_page(reader.pages[i])
                total_all_pages += (page_end - page_start)

            # 清除恶意脚本
            self.sanitize_pdf_writer(writer)

            out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=TEMP_DIR)
            writer.write(out_temp)
            out_temp.close()
            output_temp_path = out_temp.name

            # 清理输入临时文件
            for path in input_paths:
                self.clean_temp(path)

            PdfTask.objects.create(
                file_name=" | ".join(file_names),
                start_page=1,
                end_page=total_all_pages,
                status="success"
            )

            out_filename = f"合并文档_{len(file_names)}个文件.pdf"
            resp = FileResponse(open(output_temp_path, "rb"), filename=out_filename)
            resp.background = lambda p=output_temp_path: self.clean_temp(p)
            return resp

        except Exception as err:
            for path in input_paths:
                self.clean_temp(path)
            self.clean_temp(output_temp_path)
            PdfTask.objects.create(
                file_name=" | ".join([f.name for f in pdf_files]) if pdf_files else "无文件",
                start_page=1,
                end_page=0,
                status=f"多文件合并失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class RemoveTextWatermarkView(PdfBaseView):
    """独立接口：擦除PDF指定文本水印（redact永久删除文字）"""
    def remove_text_watermarks(self, input_path, output_path, watermark_list, password=""):
        doc = None
        try:
            doc = fitz.open(input_path)
            # 关闭所有脚本、危险渲染，降低漏洞风险

            if doc.is_encrypted:
                if not password:
                    raise Exception("PDF已加密，请提供打开密码")
                if not doc.decrypt(password):
                    raise Exception("PDF密码错误，解密失败")

            for page in doc:
                for watermark_text in watermark_list:
                    wt = watermark_text.strip()
                    if not wt:
                        continue
                    text_instances = page.search_for(wt)
                    for rect in text_instances:
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions(images=0)

            doc.save(output_path, garbage=4, deflate=True)
        finally:
            if doc:
                doc.close()

    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        password = request.data.get("password", "")
        watermarks_raw = request.data.getlist("watermarks")
        watermark_list = [w.strip() for w in watermarks_raw if w.strip()]

        if not pdf_file:
            return Response({"code": 400, "msg": "缺少PDF文件"}, status=status.HTTP_400_BAD_REQUEST)
        if not watermark_list:
            return Response({"code": 400, "msg": "请传入需要擦除的水印文本"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        output_path = ""
        try:
            _, total, input_path = self.load_pdf_reader(pdf_file, password)

            out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=TEMP_DIR)
            out_temp.close()
            output_path = out_temp.name

            self.remove_text_watermarks(input_path, output_path, watermark_list, password)
            self.clean_temp(input_path)

            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=1,
                end_page=total,
                status="success"
            )

            resp = FileResponse(open(output_path, "rb"), filename=f"{pdf_file.name.replace('.pdf','')}_去水印.pdf")
            resp.background = lambda p=output_path: self.clean_temp(p)
            return resp

        except Exception as err:
            self.clean_temp(input_path)
            self.clean_temp(output_path)
            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=1,
                end_page=0,
                status=f"去水印失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class PdfToImageView(PdfBaseView):
    """PDF指定页码转图片打包ZIP"""
    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        img_type = request.data.get("type", "jpg")
        quality = request.data.get("quality", 85)
        password = request.data.get("password", "")
        page1 = request.data.get("page1")
        page2 = request.data.get("page2")

        if not pdf_file:
            return Response({"code": 400, "msg": "缺少PDF文件"}, status=status.HTTP_400_BAD_REQUEST)
        if img_type not in ("jpg", "png"):
            return Response({"code": 400, "msg": "type仅支持 jpg / png"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quality = int(quality)
        except ValueError:
            quality = 85
        quality = max(1, min(100, quality))

        try:
            page1 = int(page1)
            page2 = int(page2)
        except (ValueError, TypeError):
            return Response({"code": 400, "msg": "页码必须是数字"}, status=status.HTTP_400_BAD_REQUEST)

        input_temp_path = ""
        zip_temp_path = ""
        doc = None
        try:
            _, total, input_temp_path = self.load_pdf_reader(pdf_file, password)

            s_idx = page1 - 1
            e_idx = page2 - 1
            if not (0 <= s_idx < total and 0 <= e_idx < total and s_idx <= e_idx):
                raise Exception(f"页码超出范围，当前PDF共{total}页")

            doc = fitz.open(input_temp_path)

            if doc.is_encrypted:
                if not doc.authenticate(password):
                    raise Exception("PDF密码错误，无法解密")

            zip_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=TEMP_DIR)
            zip_temp_path = zip_file.name
            zip_file.close()

            with zipfile.ZipFile(zip_temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for page_idx in range(s_idx, e_idx + 1):
                    page = doc.load_page(page_idx)
                    pix = page.get_pixmap(dpi=150)
                    real_page_num = page_idx + 1
                    img_suffix = f".{img_type}"

                    img_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=img_suffix, dir=TEMP_DIR)
                    img_tmp_path = img_tmp.name
                    img_tmp.close()

                    if img_type == "jpg":
                        pix.pil_save(img_tmp_path, "JPEG", quality=quality)
                    else:
                        pix.pil_save(img_tmp_path, "PNG")

                    zf.write(img_tmp_path, f"page_{real_page_num}{img_suffix}")
                    self.clean_temp(img_tmp_path)

            doc.close()
            doc = None
            self.clean_temp(input_temp_path)

            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=page1,
                end_page=page2,
                status="success"
            )

            download_name = f"{pdf_file.name.rsplit('.pdf', 1)[0]}_page{page1}-{page2}_图片合集.zip"
            resp = FileResponse(open(zip_temp_path, "rb"), filename=download_name)
            resp.background = lambda p=zip_temp_path: self.clean_temp(p)
            return resp

        except Exception as err:
            try:
                if doc is not None:
                    doc.close()
            except Exception:
                pass
            self.clean_temp(input_temp_path)
            self.clean_temp(zip_temp_path)

            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "unknown.pdf",
                start_page=page1,
                end_page=0,
                status=f"转换失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)
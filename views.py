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


from .models import PdfTask


class PdfBaseView(APIView):
    """公共基类，抽取所有PDF通用逻辑，两个视图复用"""
    parser_classes = [MultiPartParser]

    def load_pdf_reader(self, file_obj, password=""):
        """
        读取PDF、解密，返回reader、总页数、临时文件路径
        """
        temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
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

    def clean_temp(self, path):
        """清理临时文件"""
        if os.path.exists(path):
            os.remove(path)


class SplitPdfView(PdfBaseView):
    """原有：指定起止页，输出单个PDF"""

    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        page1 = request.data.get("page1")
        page2 = request.data.get("page2")
        password = request.data.get("password", "")

        # 参数校验
        if not pdf_file or page1 is None or page2 is None:
            return Response({"code": 400, "msg": "缺少PDF文件或页码参数"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            page1 = int(page1)
            page2 = int(page2)
        except ValueError:
            return Response({"code": 400, "msg": "页码必须是数字"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        try:
            # 复用基类读取解密逻辑
            reader, total, input_path = self.load_pdf_reader(pdf_file, password)

            s_idx = page1 - 1
            e_idx = page2 - 1
            if not (0 <= s_idx < total and 0 <= e_idx < total and s_idx <= e_idx):
                raise Exception(f"页码超出范围，当前PDF共{total}页")

            writer = PyPDF2.PdfWriter()
            for i in range(s_idx, e_idx + 1):
                writer.add_page(reader.pages[i])

            temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            writer.write(temp_out)
            temp_out.close()
            output_path = temp_out.name

            # 日志
            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=page1,
                end_page=page2,
                status="success"
            )
            self.clean_temp(input_path)

            resp = FileResponse(open(output_path, "rb"),
                                filename=f"{pdf_file.name.replace('.pdf', '')}_{page1}-{page2}.pdf")
            resp.background = lambda: self.clean_temp(output_path)
            return resp

        except Exception as err:
            if input_path:
                self.clean_temp(input_path)
            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "unknown.pdf",
                start_page=page1,
                end_page=page2,
                status=f"失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class SplitAllPageZipView(PdfBaseView):
    """新增：全部页面单独PDF，打包ZIP返回，完全复用PDF读取/解密逻辑"""

    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        password = request.data.get("password", "")

        if not pdf_file:
            return Response({"code": 400, "msg": "缺少PDF文件"}, status=status.HTTP_400_BAD_REQUEST)

        input_path = ""
        try:
            # 复用基类解密、读取PDF
            reader, total, input_path = self.load_pdf_reader(pdf_file, password)

            # 内存生成zip，不落地临时文件
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for page_num in range(1, total + 1):
                    idx = page_num - 1
                    writer = PyPDF2.PdfWriter()
                    writer.add_page(reader.pages[idx])
                    page_buf = io.BytesIO()
                    writer.write(page_buf)
                    page_buf.seek(0)
                    zf.writestr(f"{page_num}.pdf", page_buf.getvalue())

            zip_buffer.seek(0)
            self.clean_temp(input_path)

            # 记录任务日志（起止页填全部）
            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=1,
                end_page=total,
                status="success"
            )

            # 返回zip二进制流
            origin_name = pdf_file.name.replace(".pdf", "")
            resp = HttpResponse(zip_buffer, content_type="application/zip")
            resp["Content-Disposition"] = f'attachment; filename="{origin_name}_all.zip"'
            return resp

        except Exception as err:
            if input_path:
                self.clean_temp(input_path)
            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "未知文件",
                start_page=1,
                end_page=0,
                status=f"失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)

class RemoveKeywordView(PdfBaseView):
    def remove_text_watermarks(self, input_path, output_path, watermark_list, password=""):
        """
        批量擦除PDF文本水印，使用redact永久移除文字，保留图片/矢量图
        :param input_path: 原始 PDF 路径
        :param output_path: 输出 PDF 路径
        :param watermark_list: 包含所有需要去除的水印文本的列表
        :param password: PDF打开密码，加密文件必填
        """
        doc = None
        try:
            doc = fitz.open(input_path)
            # 解密处理
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
                # 执行擦除，保留图片
                page.apply_redactions(images=0)

            doc.save(output_path, garbage=4, deflate=True)
        finally:
            if doc:
                doc.close()

    def post(self, request):
        # 接收多文件数组
        pdf_files = request.FILES.getlist("pdf_files")
        # FormData 普通参数必须用 POST.getlist
        start_list = request.POST.getlist("starts")
        end_list = request.POST.getlist("ends")
        pwd_list = request.POST.getlist("passwords")

        # 打印调试，看后端实际收到的数据
        print("文件数量：", len(pdf_files))
        print("start数组：", start_list)
        print("end数组：", end_list)
        print("pwd数组：", pwd_list)

        # 基础校验
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

            # 循环处理每一个上传的PDF
            for idx in range(len(pdf_files)):
                f = pdf_files[idx]
                s_str = start_list[idx]
                e_str = end_list[idx]
                # 修复密码None问题
                raw_pwd = pwd_list[idx] if idx < len(pwd_list) else ""
                pwd = str(raw_pwd).strip() if raw_pwd is not None else ""
                file_names.append(f.name)

                # 页码转数字
                try:
                    page_start = int(s_str) - 1
                    page_end = int(e_str)
                except ValueError:
                    raise Exception(f"第{idx + 1}个PDF页码必须为数字")

                # 解密读取PDF
                reader, total, temp_in_path = self.load_pdf_reader(f, pwd)
                input_paths.append(temp_in_path)

                # 页码范围校验
                if not (0 <= page_start < total and page_end <= total and page_start < page_end):
                    raise Exception(f"【{f.name}】页码越界，文档总页数{total}")

                # 截取页面写入合并器
                for i in range(page_start, page_end):
                    writer.add_page(reader.pages[i])
                total_all_pages += (page_end - page_start)

            # 生成合并后的临时PDF
            out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            writer.write(out_temp)
            out_temp.close()
            output_temp_path = out_temp.name

            # 清理所有输入临时文件
            for path in input_paths:
                self.clean_temp(path)

            # 写入操作日志
            PdfTask.objects.create(
                file_name=" | ".join(file_names),
                start_page=1,
                end_page=total_all_pages,
                status="success"
            )

            # 返回下载
            out_filename = f"合并文档_{len(file_names)}个文件.pdf"
            resp = FileResponse(open(output_temp_path, "rb"), filename=out_filename)
            resp.background = lambda: self.clean_temp(output_temp_path)
            return resp

        except Exception as err:
            # 清理全部临时文件
            for path in input_paths:
                self.clean_temp(path)
            if output_temp_path:
                self.clean_temp(output_temp_path)
            # 失败日志
            PdfTask.objects.create(
                file_name=" | ".join([f.name for f in pdf_files]) if pdf_files else "无文件",
                start_page=1,
                end_page=0,
                status=f"多文件合并失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)

class MergeAllView(PdfBaseView):
    """支持任意数量PDF，各自截取指定页面后合并成一个文件"""
    def post(self, request):
        # 接收多文件数组
        pdf_files = request.FILES.getlist("pdf_files")
        start_list = request.POST.getlist("starts")
        end_list = request.POST.getlist("ends")
        pwd_list = request.POST.getlist("passwords")

        print("文件数量：", len(pdf_files))
        print("start数组：", start_list)
        print("end数组：", end_list)
        print("pwd数组：", pwd_list)
        # 基础校验
        if len(pdf_files) == 0:
            return Response({"code": 400, "msg": "请至少上传一个PDF文件"}, status=status.HTTP_400_BAD_REQUEST)
        if not (len(pdf_files) == len(start_list) == len(end_list)):
            return Response({"code": 400, "msg": "文件数量与页码数组数量不匹配"}, status=status.HTTP_400_BAD_REQUEST)

        input_paths = []  # 存放所有PDF临时路径，统一清理
        output_temp_path = ""
        total_all_pages = 0
        file_names = []

        try:
            writer = PyPDF2.PdfWriter()

            # 循环处理每一个上传的PDF
            for idx in range(len(pdf_files)):
                f = pdf_files[idx]
                s_str = start_list[idx]
                e_str = end_list[idx]
                pwd = pwd_list[idx] if idx < len(pwd_list) else ""
                file_names.append(f.name)

                # 页码转数字
                try:
                    page_start = int(s_str) - 1
                    page_end = int(e_str)
                except ValueError:
                    raise Exception(f"第{idx+1}个PDF页码必须为数字")

                # 解密读取PDF
                reader, total, temp_in_path = self.load_pdf_reader(f, pwd)
                input_paths.append(temp_in_path)

                # 页码范围校验
                if not (0 <= page_start < total and page_end <= total and page_start < page_end):
                    raise Exception(f"【{f.name}】页码越界，文档总页数{total}")

                # 截取页面写入合并器
                for i in range(page_start, page_end):
                    writer.add_page(reader.pages[i])
                total_all_pages += (page_end - page_start)

            # 生成合并后的临时PDF
            out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            writer.write(out_temp)
            out_temp.close()
            output_temp_path = out_temp.name

            # 清理所有输入临时文件
            for path in input_paths:
                self.clean_temp(path)

            # 写入操作日志
            PdfTask.objects.create(
                file_name=" | ".join(file_names),
                start_page=1,
                end_page=total_all_pages,
                status="success"
            )

            # 返回下载
            out_filename = f"合并文档_{len(file_names)}个文件.pdf"
            resp = FileResponse(open(output_temp_path, "rb"), filename=out_filename)
            resp.background = lambda: self.clean_temp(output_temp_path)
            return resp

        except Exception as err:
            # 清理全部临时文件
            for path in input_paths:
                self.clean_temp(path)
            if output_temp_path:
                self.clean_temp(output_temp_path)
            # 失败日志
            PdfTask.objects.create(
                file_name=" | ".join([f.name for f in pdf_files]) if pdf_files else "无文件",
                start_page=1,
                end_page=0,
                status=f"多文件合并失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class PdfToImageView(PdfBaseView):
    def post(self, request):
        pdf_file = request.FILES.get("pdf_file")
        img_type = request.data.get("type", "jpg")
        quality = request.data.get("quality", 85)
        password = request.data.get("password", "")
        # 接收前端分页参数
        page1 = request.data.get("page1")
        page2 = request.data.get("page2")

        # 参数校验
        if not pdf_file:
            return Response({"code": 400, "msg": "缺少PDF文件"}, status=status.HTTP_400_BAD_REQUEST)
        if img_type not in ("jpg", "png"):
            return Response({"code": 400, "msg": "type仅支持 jpg / png"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quality = int(quality)
        except ValueError:
            quality = 85
        quality = max(1, min(100, quality))

        # 页码校验逻辑（复用你拆分PDF的规则）
        try:
            page1 = int(page1)
            page2 = int(page2)
        except (ValueError, TypeError):
            return Response({"code": 400, "msg": "页码必须是数字"}, status=status.HTTP_400_BAD_REQUEST)

        input_temp_path = ""
        zip_temp_path = ""
        doc = None
        try:
            # 1. 保存上传PDF到临时文件，解密读取
            _, total, input_temp_path = self.load_pdf_reader(pdf_file, password)

            # 页码边界校验
            s_idx = page1 - 1
            e_idx = page2 - 1
            if not (0 <= s_idx < total and 0 <= e_idx < total and s_idx <= e_idx):
                raise Exception(f"页码超出范围，当前PDF共{total}页")

            # 2. fitz 打开PDF
            doc = fitz.open(input_temp_path)
            if doc.is_encrypted:
                if not doc.authenticate(password):
                    raise Exception("PDF密码错误，无法解密")

            # 3. 创建临时zip包
            zip_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            zip_temp_path = zip_file.name
            zip_file.close()

            # 循环生成图片写入zip
            with zipfile.ZipFile(zip_temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for page_idx in range(s_idx, e_idx + 1):
                    page = doc.load_page(page_idx)
                    pix = page.get_pixmap(dpi=150)
                    real_page_num = page_idx + 1
                    img_suffix = f".{img_type}"

                    img_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=img_suffix)
                    img_tmp_path = img_tmp.name
                    img_tmp.close()

                    # 修复quality不兼容问题：使用pil_save
                    if img_type == "jpg":
                        pix.pil_save(img_tmp_path, "JPEG", quality=quality)
                    else:
                        pix.pil_save(img_tmp_path, "PNG")

                    zf.write(img_tmp_path, f"page_{real_page_num}{img_suffix}")
                    os.unlink(img_tmp_path)

            # 关键：先关闭fitz文档，释放文件锁
            doc.close()
            doc = None

            # 记录日志
            PdfTask.objects.create(
                file_name=pdf_file.name,
                start_page=page1,
                end_page=page2,
                status="success"
            )
            # 现在再删除临时PDF，不会报占用
            self.clean_temp(input_temp_path)

            # 返回zip下载
            download_name = f"{pdf_file.name.rsplit('.pdf', 1)[0]}_page{page1}-{page2}_图片合集.zip"
            resp = FileResponse(open(zip_temp_path, "rb"), filename=download_name)
            resp.background = lambda: self.clean_temp(zip_temp_path)
            return resp

        except Exception as err:
            # 异常分支先关闭文档释放锁
            try:
                if doc is not None:
                    doc.close()
                    doc = None
            except:
                pass
            if input_temp_path and os.path.exists(input_temp_path):
                self.clean_temp(input_temp_path)
            if zip_temp_path and os.path.exists(zip_temp_path):
                self.clean_temp(zip_temp_path)

            PdfTask.objects.create(
                file_name=pdf_file.name if pdf_file else "unknown.pdf",
                start_page=page1,
                end_page=0,
                status=f"转换失败:{str(err)}"
            )
            return Response({"code": 400, "msg": str(err)}, status=status.HTTP_400_BAD_REQUEST)
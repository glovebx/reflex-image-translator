from app.db.database import Database
import asyncio

import base64
from datetime import datetime

import html
import httpx
import io
import json
import mimetypes
import os
from paddleocr import PaddleOCR
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import re
import reflex as rx
import requests
import tempfile
from typing import List, Dict, Tuple, Optional

import unicodedata
import uuid

# en_ocr = PaddleOCR(use_angle_cls=True, lang='en') # need to run only once to download and load model into memory
# loaded_ocr_models = {'en': en_ocr}
loaded_ocr_models = {}

# gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent"
translate_url = os.getenv('TRANSLATOR_URL')

_google_translator_languages = {
  "中文": "zh-CN",
  "繁体中文": "zh-TW",
  "英语": "en",
  "法语": "fr",
  "德语": "de",
  "日语": "ja",
  "韩语": "ko",
  "意大利语": "it",
  "西班牙语": "es",
  "俄语": "ru",
  "阿拉伯语": "ar",
}

_paddle_ocr_languages = {
  "中文": "ch",
  "繁体中文": "chinese_cht",  
  "英语": "en",
  "法语": "fr",
  "德语": "german",
  "日语": "japan",
  "韩语": "korean",
  "意大利语": "it",
  "西班牙语": "es",
  "俄语": "ru",
  "阿拉伯语": "ar",
}

def load_paddle_ocr(lang):
    if lang in loaded_ocr_models.keys():
        return
    
    if lang in _paddle_ocr_languages.values():
        ocr = PaddleOCR(use_angle_cls=True, lang=lang)
        loaded_ocr_models[lang] = ocr

def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

def device_guess(width: int) -> str:
    if width < 520:
        return "phone"
    elif width < 768:
        return "phone-landscape"
    elif width < 1024:
        return "tablet"
    elif width < 1280:
        return "tablet-landscape"
    elif width < 1640:
        return "laptop"
    else:
        return "desktop"
    
def get_font(image, text, width, height):

    # Default values at start
    # font_size = None  # For font size
    font = None  # For object truetype with correct font size
    box = None  # For version 8.0.0
    x = 0
    y = 0

    draw = ImageDraw.Draw(image)  # Create a draw object

    font_path = Path(__file__).parent.parent / "assets/fonts/SimHei.ttc"

    # Test for different font sizes
    for size in range(1, 500):

        # Create new font
        # new_font = ImageFont.load_default(size=font_size)
        new_font = ImageFont.truetype(font_path.as_posix(), size, encoding="utf-8") 

        # Calculate bbox for version 8.0.0
        new_box = draw.textbbox((0, 0), text, font=new_font)

        # Calculate width and height
        new_w = new_box[2] - new_box[0]  # Bottom - Top
        new_h = new_box[3] - new_box[1]  # Right - Left

        # If too big then exit with previous values
        if new_w > width or new_h > height:
            break

        # Set new current values as current values
        # font_size = size
        font = new_font
        box = new_box
        w = new_w
        h = new_h

        # Calculate position (minus margins in box)
        x = (width - w) // 2 - box[0]  # Minus left margin
        y = (height - h) // 2 - box[1]  # Minus top margin

    return font, x, y


def add_discoloration(color, strength, default_color=(245, 245, 245)):
    # Adjust RGB values to add discoloration

    # if isinstance(color, (Tuple, List)):
    #     if (len(color)) == 4:
    #         r, g, b, _ = color
    #     else:
    #         r, g, b = color
    # else:
    #     r, g, b = 245, 245, 245

    try:
        # 尝试将颜色值解包为4个元素，并忽略最后一个元素（alpha通道）
        r, g, b, _ = color
    except (TypeError, ValueError):
        try:
            # 尝试将颜色值解包为3个元素
            r, g, b = color
        except (TypeError, ValueError):
            # 如果解包失败，使用默认值
            r, g, b = default_color

    r = max(0, min(255, r + strength))  # Ensure RGB values are within valid range
    g = max(0, min(255, g + strength))
    b = max(0, min(255, b + strength))
    
    if r == 255 and g == 255 and b == 255:
        r, g, b = default_color

    return (r, g, b)


def get_background_color(image, x_min, y_min, x_max, y_max):
    # Define the margin for the edges
    margin = 10

    # Crop a small region around the edges of the bounding box
    edge_region = image.crop(
        (
            max(x_min - margin, 0),
            max(y_min - margin, 0),
            min(x_max + margin, image.width),
            min(y_max + margin, image.height),
        )
    )

    # Find the most common color in the cropped region
    edge_colors = edge_region.getcolors(edge_region.size[0] * edge_region.size[1])
    background_color = max(edge_colors, key=lambda x: x[0])[1]

    # Add a bit of discoloration to the background color
    background_color = add_discoloration(background_color, 40)

    return background_color


def get_text_fill_color(background_color):
    # Calculate the luminance of the background color
    luminance = (
        0.299 * background_color[0]
        + 0.587 * background_color[1]
        + 0.114 * background_color[2]
    ) / 255

    # Determine the text color based on the background luminance
    if luminance > 0.5:
        return "black"  # Use black text for light backgrounds
    else:
        return "white"  # Use white text for dark backgrounds
    
def find_min_max(coordinates):
    """
    找到二维坐标列表中x和y的最小值和最大值

    Args:
        coordinates: 二维坐标列表

    Returns:
        一个元组，包含最小x, 最大x, 最小y, 最大y
    """

    min_x = coordinates[0][0]
    max_x = coordinates[0][0]
    min_y = coordinates[0][1]
    max_y = coordinates[0][1]

    for x, y in coordinates:
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)

    return min_x, max_x, min_y, max_y

def replace_text_with_translation(image_path, ocr_results):
    # Open the image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    width, height = image.size
    # # Load a font
    # font = ImageFont.load_default()

    # Replace each text box with translated text
    for ocr_result in ocr_results:

        translated = ocr_result[1][1]
        if not translated:
            continue

        # Set initial values
        # [[8.0, 128.0], [368.0, 129.0], [368.0, 143.0], [8.0, 142.0]]
        coordinates = ocr_result[0]

        x_min, x_max, y_min, y_max = find_min_max(coordinates)

        if x_max > width:
            x_max = width
        if y_max > height:
            y_max = height

        # Find the most common color in the text region
        background_color = get_background_color(image, x_min, y_min, x_max, y_max)

        # Draw a rectangle to cover the text region with the original background color
        draw.rectangle(((x_min, y_min), (x_max, y_max)), fill=background_color)

        # Calculate font size, box
        font, x, y = get_font(image, translated, x_max - x_min, y_max - y_min)

        # Draw the translated text within the box
        draw.text(
            (x_min + x, y_min + y),
            translated,
            fill=get_text_fill_color(background_color),
            font=font,
        )

    return image
    
def compress_image_to_size(image_path, target_size_kb=500):
    """
    使用 PIL 压缩图片到指定大小以下并覆盖原文件。

    Args:
        image_path: 图片路径。
        target_size_kb: 目标文件大小，单位 KB。
    """

    temp_path = "temp_compressed.jpg"  # 临时文件路径    
    try:
        original_size_kb = os.path.getsize(image_path) / 1024  # 获取原始文件大小（KB）
        if original_size_kb <= target_size_kb:
            print(f"图片 {image_path} 已小于 {target_size_kb}KB，无需压缩。")
            return

        img = Image.open(image_path)
        # 如果不是RGB模式，则转换为RGB模式，避免保存时出错
        if img.mode != "RGB":
            img = img.convert("RGB")

        quality = 90  # 初始 JPEG 质量

        while True:
            img.save(temp_path, "JPEG", optimize=True, quality=quality)
            compressed_size_kb = os.path.getsize(temp_path) / 1024

            if compressed_size_kb <= target_size_kb:
                os.replace(temp_path, image_path)  # 覆盖原文件
                print(f"图片 {image_path} 已压缩到 {compressed_size_kb:.2f}KB (原大小: {original_size_kb:.2f}KB)，质量为 {quality}。")
                break

            quality -= 5  # 每次降低质量 5
            if quality <= 0:  # 防止 quality 降到 0 以下
                print(f"无法将图片 {image_path} 压缩到 {target_size_kb}KB 以下，已尽力压缩至 {compressed_size_kb:.2f}KB。")
                os.replace(temp_path, image_path)
                break
    except FileNotFoundError:
        print(f"文件未找到: {image_path}")
    except OSError as e: # 处理文件路径错误
        print(f"文件路径错误：{e}")
    except Exception as e:
        print(f"发生错误: {e}")
    finally: # 确保删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

class State(rx.State):

    viewport_width: int = 0
    viewport_height: int = 0    

    error: str = ""
    progress: int = 0
    uploading: bool = False
    processing: bool = False

    ajs_visitor_id: str = rx.LocalStorage(name="reflex_visitor_id")
    current_user: dict = {}
    show_auth_dialog = False
    login_status: int = 0
    login_message = ""
    login_processing: bool = False

    
    google_translator_languages: List[str] = [key for key, _ in _google_translator_languages.items()]
    # print(google_translator_languages)

    source_language: str = "英语"  # 默认源语言为英文
    target_language: str = "中文"  # 默认目标语言为中文

    previewable_images: List[Tuple[str, str]] = []
    show_image_preview_modal: bool = False

    progress_history: List[Tuple[str, str]] = []
    max_progress_history_length = 30

    start_time_sec = 0

    @rx.event
    def set_viewport(self, width: int, height: int) -> None:
        self.viewport_width = width
        self.viewport_height = height

    @rx.event
    async def handle_paste(self, data: list[tuple[str, str]]):
        for mime_type, item in data:

            if not mime_type.startswith('image/'):
                continue

            async for value in self.handle_submit_files(base64_image=item):
                print('正在处理剪贴板的图片...')
                yield
            break

            # print(item)

            # file_extension = ".png"
            # if item.startswith("data:image/"):
            #     # 分割 data URI 字符串
            #     header, b64_encoded = item.split(",", 1)

            #     # 获取 mime 类型 (例如 image/png, image/jpeg)
            #     mime_type = header.split(";")[0].split(":")[1]

            #     #根据mime类型设置后缀名
            #     if "png" in mime_type:
            #         file_extension = ".png"
            #     elif "jpeg" in mime_type or "jpg" in mime_type:
            #         file_extension = ".jpg"
            #     elif "gif" in mime_type:
            #         file_extension = ".gif"
            # else:
            #     b64_encoded = item

            # _, filename = tempfile.mkstemp()
            # filename = os.path.basename(f"{filename}{file_extension}")

            # # 尝试解码 base64 数据
            # try:
            #     # 尝试解码，处理可能的异常
            #     image_data = base64.b64decode(b64_encoded)
            # except (base64.binascii.Error, UnicodeDecodeError):
            #     print("剪贴板内容不是有效的 base64 编码的图像数据。")
            #     return
            
            # upload_dir = "uploaded_files"
            # os.makedirs(upload_dir, exist_ok=True)
            # file_path = os.path.join(upload_dir, filename)

            # # 使用io.BytesIO处理内存中的图像数据
            # try:
            #     image = Image.open(io.BytesIO(image_data))

            #     # 自动判断文件类型并保存
            #     image.save(file_path)
            #     print(f"图像已保存到 {file_path}")
            # except Exception as e:
            #     print(f"保存图像时发生错误: {e}")
            #     return
        
    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        
        async for value in self.handle_submit_files(files=files):
            print('正在处理上传的图片...')
            yield
        # self.error = ''

        # if not files:
        #     return

        # if not self.current_user['session_id']:
        #     # 需要登录
        #     self.error = "请先登录"
        #     return

        # if files:
        # # try:
        #     file = files[0]
        #     upload_dir = "uploaded_files"
        #     os.makedirs(upload_dir, exist_ok=True)
            
        #     filename = file.filename
        #     file_path = os.path.join(upload_dir, filename)
        #     upload_data = await file.read()
            
        #     with open(file_path, "wb") as f:
        #         f.write(upload_data)

        #     compress_image_to_size(file_path)    

        #     self.start_time_sec = datetime.now().timestamp()

        #     ocr_results = None
        #     step = 1
        #     async for value in self.process_file(file_path, filename):
        #         print('processing....', f"第{step}步")
        #         step += 1
        #         if value:
        #             # 返回了text_blocks
        #             ocr_results = value
        #         yield    

        #     if not ocr_results:
        #         seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
        #         self.progress_history.append(("处理结束", f"{seconds}秒"))
        #         yield
        #     else:
        #         # Replace text with translated text
        #         image = replace_text_with_translation(file_path, ocr_results)
        #         # out_file_path = f"{file_path}.png"
        #         # image.save(out_file_path)

        #         buffered = io.BytesIO()
        #         image.save(buffered, format="PNG")
        #         b64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")  

        #         self.previewable_images.append((f"data:image/png;base64,{b64_image}", f"{filename}.png"))

        #         seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)                
        #         self.progress_history.append(("翻译完成", f"{seconds}秒"))
        #         yield
            
        # # except Exception as e:
        # #     print(e)
        # #     self.error = f"翻译失败: {str(e)}"
    
    def handle_upload_progress(self, progress: dict):
        self.uploading = True
        self.progress = round(progress["progress"] * 100)
        if self.progress >= 100:
            self.uploading = False
        print('self.progress==', self.progress)

    async def handle_submit_files(self, files: list[rx.UploadFile]=None, base64_image: str=None):
        self.error = ''

        if not files and not base64_image:
            return

        if not self.current_user.get('session_id'):
            # 需要登录
            self.error = "请先登录"
            return
        
        self.start_time_sec = datetime.now().timestamp()

        seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
        self.progress_history = [("有新图片", f"{seconds}秒")]
        yield

        upload_dir = "uploaded_files"
        os.makedirs(upload_dir, exist_ok=True)
        # try:
        if files:
            file = files[0]
            filename = file.filename
            file_path = os.path.join(upload_dir, filename)

            upload_data = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(upload_data)
        else:
            file_extension = ".png"
            if base64_image.startswith("data:image/"):
                # 分割 data URI 字符串
                header, b64_encoded = base64_image.split(",", 1)

                # 获取 mime 类型 (例如 image/png, image/jpeg)
                mime_type = header.split(";")[0].split(":")[1]

                #根据mime类型设置后缀名
                if "png" in mime_type:
                    file_extension = ".png"
                elif "jpeg" in mime_type or "jpg" in mime_type:
                    file_extension = ".jpg"
                elif "gif" in mime_type:
                    file_extension = ".gif"
            else:
                b64_encoded = base64_image
            # 尝试解码 base64 数据
            try:
                # 尝试解码，处理可能的异常
                upload_data = base64.b64decode(b64_encoded)
            except (base64.binascii.Error, UnicodeDecodeError):
                print("剪贴板内容不是有效的 base64 编码的图像数据。")
                raise            

            _, filename = tempfile.mkstemp()
            filename = os.path.basename(f"{filename}{file_extension}")

            # upload_dir = "uploaded_files"
            # os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)

            # 使用io.BytesIO处理内存中的图像数据
            try:
                image = Image.open(io.BytesIO(upload_data))

                # 自动判断文件类型并保存
                image.save(file_path)
                print(f"图像已保存到 {file_path}")
            except Exception as e:
                print(f"保存图像时发生错误: {e}")
                raise

        compress_image_to_size(file_path)    

        self.start_time_sec = datetime.now().timestamp()

        ocr_results = None
        step = 1
        async for value in self.process_file(file_path, filename):
            print('processing....', f"第{step}步")
            step += 1
            if value:
                # 返回了text_blocks
                ocr_results = value
            yield    

        if not ocr_results:
            seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
            self.progress_history.append(("处理结束", f"{seconds}秒"))
            yield
        else:
            # Replace text with translated text
            image = replace_text_with_translation(file_path, ocr_results)
            # out_file_path = f"{file_path}.png"
            # image.save(out_file_path)

            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            b64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")  

            self.previewable_images.append((f"data:image/png;base64,{b64_image}", f"{filename}.png"))

            seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)                
            self.progress_history.append(("翻译完成", f"{seconds}秒"))
            yield
            
        # except Exception as e:
        #     print(e)
        #     self.error = f"翻译失败: {str(e)}"

    async def process_file(self, file_path, filename):
        self.processing = True
        yield

        mime_type, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            b64_image = encoded_string.decode("utf-8")  # Decode to string

        if len(self.previewable_images) > 6:
            self.previewable_images = self.previewable_images[-2:]
        yield

        self.previewable_images.append((f"data:{mime_type};base64,{b64_image}", filename))

        seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
        self.progress_history.append(("正在识别图片", f"{seconds}秒"))
        yield

        # if len(self.progress_history) > self.max_progress_history_length:
        #     self.progress_history = self.progress_history[-self.max_progress_history_length:]
        # yield

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=30.0)) as client:
            try:
                # # 需要用大模型判断图片中文字的语言
                # # 根据返回语言，判断paddle是否载入了相应模型，否则等待载入
                # headers = {
                #     "Content-Type": "application/json",
                #     "Token": "v1beta.20241220_200"
                #     },
                # input_payload = {
                #     "lang": "zh", 
                #     "contentFormat": "lang_detect",
                #     "inlineData": {
                #         "mimeType": mime_type,
                #         "data": b64_image
                #         }
                # }
                # response = await client.post(
                #     gemini_url,
                #     json=input_payload,
                #     headers=headers,
                # )
                # response.raise_for_status()

                # print(response.text)

                # result = response.json()
                # src_language = result.get('text').strip('\n ') if 'text' in result else 'en'
                # yield

                # 载入对应的语言
                seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
                self.progress_history.append(("正在载入对应的语言模型", f"{seconds}秒"))
                yield

                ocr_lang = _paddle_ocr_languages.get(self.source_language)

                print(ocr_lang)

                load_paddle_ocr(lang=ocr_lang)
                yield

                ocr_engine = loaded_ocr_models[ocr_lang]
                # 以下是翻译功能                
                ocr_resultss = ocr_engine.ocr(file_path, cls=True)

                ocr_results = ocr_resultss[0] if ocr_resultss else []

                seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
                self.progress_history.append((ocr_results and "图片识别成功，正在翻译" or "图片识别完成，没有文字", f"{seconds}秒"))
                yield

                translated_results = []
                if ocr_results:
                    for ocr_result in ocr_results:
                        text_block = ocr_result[1] if len(ocr_result) > 1 else None
                        source_text = text_block[0] if text_block else ''
                        if not source_text:
                            text_block = (source_text, '')
                            translated_results.append([ocr_result[0], text_block])
                            continue
                        # get from cache
                        cache_results = Database.get_instance().get_translated_text(source_text)
                        if cache_results:
                            result = cache_results[0][0]
                        else:
                            src_language = _google_translator_languages.get(self.source_language) or 'en'
                            dst_language = _google_translator_languages.get(self.target_language) or 'zh-CN'

                            input_payload = {
                                'sl': src_language,
                                'tl': dst_language, 
                                'hl': dst_language, 
                                'q': source_text
                            }

                            print(input_payload)

                            response = await client.get(
                                translate_url,
                                params=input_payload,
                                headers={
                                    "User-Agent": "Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)"  # noqa: E501
                                    },
                                follow_redirects=True
                            )

                            response_text = response.text
                            re_result = re.findall(
                                r'(?s)class="(?:t0|result-container)">(.*?)<', response_text
                            )
                            if response.status_code == 400:
                                result = "IRREPARABLE TRANSLATION ERROR"
                            else:
                                result = html.unescape(re_result[0])

                            result = remove_control_characters(result)

                            Database.get_instance().add_translated_text(source_text, result)

                        text_block = (source_text, result)
                        translated_results.append([ocr_result[0], text_block])

                    yield translated_results

            except (httpx.RequestError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPStatusError) as e:
                seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
                self.progress_history.append(("服务器连接错误", f"{seconds}秒"))
            except asyncio.CancelledError:
                seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
                self.progress_history.append(("任务中止", f"{seconds}秒"))
            finally:
                self.processing = False
                yield

    def toggle_image_preview_modal(self):
      self.show_image_preview_modal = not self.show_image_preview_modal

    async def download_preview_image(self, data_obj):
        if data_obj:
            """Downloads the Base64 image using JavaScript."""
            js_code = f"""
                console.log('56789oiuytyujikl');
            """
            print(js_code)

            rx.run_script(js_code)
        return None

    def on_mount(self):
        """Load informations when the app starts"""

        if self.ajs_visitor_id:
            user_info = Database.get_instance().get_odoo_user(self.ajs_visitor_id)
            if user_info:
                self.current_user['uid'] = user_info[1]
                self.current_user['nickname'] = user_info[4]
                self.current_user['session_id'] = user_info[3]
        else:
            self.ajs_visitor_id = str(uuid.uuid4())


    def open_auth_dialog(self):
        self.show_auth_dialog = True

    def close_auth_dialog(self):
        self.show_auth_dialog = False

    def on_auth_mount(self):
        self.login_message = ''
        
    async def sign_in(self, form_data: dict):
        self.login_processing = True

        self.current_user = form_data
        # self.current_user["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        username = self.current_user['name']
        password = self.current_user['password']

        if not username or len(username) > 16:
            self.login_message = 'invalid username'
            self.login_processing = False
            return
        
        if not password or len(password) > 16:
            self.login_message = 'invalid password'
            self.login_processing = False
            return

        self.login_status = 1
        yield

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=30.0)) as client:
            odoo_base_url = os.getenv('BASE_URL')
            odoo_db = 'odoo14e'

            try:
                login_url = f'{odoo_base_url}/web/session/authenticate'
                login_data = {"params":{"db":odoo_db,"login":username,"password":password}}

                response = await client.post(
                    login_url,
                    json=login_data,
                )

                response.raise_for_status()

                result = response.json()
                if result.get('result'):
                    uid = result['result']['uid']
                    
                    session_id = response.cookies.get('session_id') # 获取 session_id

                    print(f'登录成功，用户 ID：{uid}')
                    print(f'Session ID: {session_id}')

                    # 现在可以使用 session 对象进行后续操作，包括调用 call_kw
                    # 示例：使用 call_kw 获取当前用户信息
                    rpc_url = f'{odoo_base_url}/web/dataset/call_kw'
                    model = 'res.users'
                    method = 'read'
                    args = [[uid], ['name', 'email']] # 参数：用户 ID 列表和要读取的字段列表
                    kwargs = {}

                    rpc_data = {
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "model": model,
                            "method": method,
                            "args": args,
                            "kwargs": kwargs,
                        },
                        "id": 1,
                    }

                    rpc_response = await client.post(rpc_url, json=rpc_data)
                    rpc_response.raise_for_status()
                    user_info = rpc_response.json()['result'][0]
                    print(f'用户信息：{user_info}')

                    Database.get_instance().add_or_update_user(self.ajs_visitor_id, uid, username, session_id, user_info['name'], '')

                    self.current_user['uid'] = uid
                    self.current_user['nickname'] = user_info['name']
                    self.current_user['session_id'] = session_id
                    # 表示session有效
                    self.login_status = 200
                    self.show_auth_dialog = False

                else:
                    self.login_message = result.get('error', {}).get('data', {}).get('message', '登录失败')
                    print(f'登录失败：{self.login_message}')
                    self.login_status = 500

            except (httpx.RequestError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPStatusError) as e:
                print(e)     
                self.login_status = 401
            finally:
                self.login_processing = False
                yield

    async def sign_out(self):
        self.current_user = {}
        self.ajs_visitor_id = ''

    # 暂时邀请制注册
    async def sign_up(self, form_data: dict):
        # Odoo 服务器地址
        url = 'http://your_odoo_server:8069'  # 替换为你的 Odoo 服务器地址
        db = 'your_database_name' # 替换为你的数据库名称

        signup_url = f'{url}/web/signup'

        # 注册用户信息
        user_data = {
            'name': 'Test User',
            'login': 'testuser@example.com',
            'password': 'testpassword',
            'confirm_password': 'testpassword',
            'db': db, #需要加入数据库名称，否则会报错
        }

        from bs4 import BeautifulSoup  # 用于解析 HTML

        try:
            # 1. 获取 csrf_token
            signup_page_response = requests.get(signup_url)
            signup_page_response.raise_for_status()
            soup = BeautifulSoup(signup_page_response.content, 'html.parser')
            csrf_token_element = soup.find('input', {'name': 'csrf_token'})
            if csrf_token_element:
                csrf_token = csrf_token_element['value']
                user_data['csrf_token'] = csrf_token
            else:
                raise Exception("无法找到 csrf_token")

            # 2. 发送注册请求
            response = requests.post(signup_url, data=user_data)  # 使用 data 参数

            response.raise_for_status()

            # 检查注册结果
            if response.status_code == 200:
                if "Congratulations" in response.text: #根据返回的html内容判断是否注册成功，不同的odoo版本返回内容可能不同
                    print("注册成功！")
                else:
                    print("注册可能失败，请检查返回内容")
                    print(response.text)
            else:
                print("注册失败，状态码:", response.status_code)
                print(response.text)
        except requests.exceptions.RequestException as e:
            print(f'请求错误：{e}')
        except Exception as e:
            print(f"其他错误：{e}")
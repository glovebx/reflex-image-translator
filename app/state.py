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
from typing import List, Dict, Tuple, Optional

import unicodedata

en_ocr = PaddleOCR(use_angle_cls=True, lang='en') # need to run only once to download and load model into memory

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
    
class State(rx.State):

    viewport_width: int = 0
    viewport_height: int = 0    

    error: str = ""
    progress: int = 0
    uploading: bool = False
    processing: bool = False

    previewable_images: List[Tuple[str, str]] = []
    show_image_preview_modal: bool = False

    progress_history: List[Tuple[str, str]] = []
    max_progress_history_length = 30

    start_time_sec = 0

    def set_viewport(self, width: int, height: int) -> None:
        self.viewport_width = width
        self.viewport_height = height

    async def handle_upload(self, files: list[rx.UploadFile]):
        self.error = ''

        if not files:
            return

        # if files:
        try:
            file = files[0]
            upload_dir = "uploaded_files"
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = file.filename
            file_path = os.path.join(upload_dir, filename)
            upload_data = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(upload_data)

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
            
        except Exception as e:
            print(e)
            self.error = f"翻译失败: {str(e)}"
    
    def handle_upload_progress(self, progress: dict):
        self.uploading = True
        self.progress = round(progress["progress"] * 100)
        if self.progress >= 100:
            self.uploading = False
        print('self.progress==', self.progress)

    async def process_file(self, file_path, filename):
        self.processing = True
        yield

        mime_type, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            b64_image = encoded_string.decode("utf-8")  # Decode to string

        if len(self.previewable_images) > 6:
            self.previewable_images = self.previewable_images[-6:]
        yield

        self.previewable_images.append((f"data:{mime_type};base64,{b64_image}", filename))

        seconds = round((datetime.now().timestamp() - self.start_time_sec), 2)
        self.progress_history = [("正在识别图片", f"{seconds}秒")]
        yield

        # if len(self.progress_history) > self.max_progress_history_length:
        #     self.progress_history = self.progress_history[-self.max_progress_history_length:]
        # yield

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=30.0)) as client:
            translate_url = "http://translate.google.com/m"

            try:
                ocr_resultss = en_ocr.ocr(file_path, cls=True)

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
                            input_payload = {
                                'sl': 'en',
                                'tl': 'zh-CN', 
                                'hl': 'zh-CN', 
                                'q': source_text
                            }

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
        pass

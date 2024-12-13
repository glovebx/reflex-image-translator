import reflex as rx
from app.state import State


def progress_line(message: str, seconds: str) -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(f"{seconds}-{message}", color="blue"),
            padding="2",
            margin_top="2",
        ),        
        class_name="flex flex-col gap-8 pb-2 group",
    )

def progress_history() -> rx.Component:
    return rx.scroll_area(
        rx.foreach(
            State.progress_history,
            lambda messages: progress_line(messages[0], messages[1]),
        ),
        scrollbars="vertical",
        class_name="w-full",
    )

def hero_section(viewport_width=0):

    return rx.hstack(
        rx.vstack(
            # Center section with prompt text and input
            rx.vstack(
                rx.text(
                    "OCR solutions powered by PaddleOCR",
                    class_name="text-4xl font-regular drop-shadow-sm text-center mb-2",
                ),
                rx.box(
                    rx.vstack(
                        rx.upload(
                            rx.vstack(
                                rx.button(
                                    "Click here to add file (up to 1)",
                                    color="rgb(107,99,246)",
                                    bg="white",
                                    border="1px solid rgb(107,99,246)",
                                ),
                                rx.text(
                                    "Or drag and drop file here",
                                    color="rgb(107,99,246)",
                                ),
                                padding="4",
                                align="center",        # 设置子元素居中
                                justify="center",      # 可选：在垂直方向上也居中                                
                            ),
                            id="upload_image",
                            multiple=False,
                            accept={
                                "image/*": [".jpg", ".png", ".jpeg", ".webp"]
                            },
                            on_drop=State.handle_upload(
                                rx.upload_files(
                                    upload_id="upload_image",
                                    on_upload_progress=State.handle_upload_progress,
                                )
                            ),
                            border="1px dashed rgb(107,99,246)",
                            border_radius="md",
                            # padding="4",
                            class_name="w-full mx-auto p-4",
                        ),
                        rx.cond(
                            State.uploading | State.processing,
                            rx.vstack(
                                rx.progress(value=State.progress),
                                rx.text(f"{State.progress}%"),
                            ),
                        ),
                        rx.cond(
                            State.error != "",
                            rx.box(
                                rx.text(State.error, color="red"),
                                padding="2",
                                margin_top="2",
                            ),
                        ), 
                        rx.cond(
                            State.previewable_images != [],
                            rx.grid(
                                rx.foreach(
                                    State.previewable_images,
                                    lambda data_obj: rx.image(src=data_obj[0], alt="thumbnail", on_click=lambda: State.download_preview_image(data_obj), style={"cursor": "pointer"}),
                                ),
                                columns="2",
                                spacing="4",
                                width="100%",
                            )                            
                        ),
                        rx.cond(
                            State.progress_history != None,
                            progress_history(),
                        ),  
                    ),
                    padding="4",
                    class_name="w-full max-w-[700px] md:max-w-[900px] mx-auto p-4 transition-all duration-300",
                ),
                spacing="4",
                padding_top="10em",
                width="100%",
                align="center",  # Centers the content horizontally
            ),
            width="100%",
            height="100vh",
            spacing="4",
        ),
        width="100%",
        height="100vh",
    )

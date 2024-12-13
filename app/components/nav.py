import reflex as rx

def nav_section():
    return (
        rx.hstack(
            rx.box(
                spacing="1",
            ),
            rx.text(
                "Image Translator",
                class_name="text-3xl md:text-5xl font-bold",
            ),
            rx.hstack(
                rx.link(
                    rx.icon("github", size=32),
                    href="https://github.com/glovebx/reflex-image-translator/",
                    is_external=True,
                ),
            ),
            class_name="w-full flex justify-between items-center px-4 md:px-8 mt-4 fixed top-0 bg-white z-50 h-16 md:h-20",
        ),
    )

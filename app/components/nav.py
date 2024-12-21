import reflex as rx
from app.state import State
from .auth import add_auth_button, add_profile_button

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
                rx.cond(
                    ~State.current_user.contains('uid'),
                    add_auth_button(),
                ),
                rx.cond(
                    State.current_user.contains('uid'),
                    add_profile_button(),
                ),
                rx.color_mode.button(size="3"),
                
                rx.link(
                    rx.icon("github", size=24),
                    href="https://github.com/glovebx/reflex-image-translator/",
                    is_external=True,
                    class_name="p-2",
                ),
            ),
            class_name="w-full flex justify-between items-center px-4 md:px-8 mt-4 fixed top-0 z-50 h-16 md:h-20",
        ),
    )

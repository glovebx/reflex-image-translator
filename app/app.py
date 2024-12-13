import reflex as rx
from .components import hero
from .components import nav
from app.state import State
from typing import List, Tuple
from app.db.database import Database

from app.resize_watcher import ResizeWatcher

# Initialize database singleton
Database.get_instance()


@rx.page(route="/", title="OCR")
def index() -> rx.Component:
    return rx.box(
        ResizeWatcher.create(on_resize=State.set_viewport),
        nav.nav_section(),
        hero.hero_section(State.viewport_width),
        on_mount=State.on_mount,
        class_name="w-full mt-4",
    )


style = {
    "font_family": "Lexend",
}


app = rx.App(
    style=style,
    stylesheets=["/fonts/font.css"],
    theme=rx.theme(
        appearance="light",
    ),
)

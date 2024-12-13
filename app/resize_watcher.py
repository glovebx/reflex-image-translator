import reflex as rx
from app.state import State

class ResizeWatcher(rx.Fragment):
    """
    A component that watches the window size and updates the state.
    
    The only event trigger in `on_resize` which is called once when the component mounts
    and again each time the viewport dimensions change.
    """

    on_resize: rx.EventHandler[lambda width, height: [width, height]]

    def _exclude_props(self) -> list[str]:
        return ["on_resize"]

    def add_imports(self) -> dict[str, str]:
        return {"react": "useEffect"}

    def add_hooks(self) -> list[str]:
        """Register backend on_resize as a handler for the browser window resize event."""
        on_resize = self.event_triggers["on_resize"]
        if isinstance(on_resize, rx.EventChain):
            on_resize = rx.utils.format.wrap(
                rx.utils.format.format_prop(on_resize).strip("{}"),
                "(",
            )
        return [
            """
            useEffect(() => {
                function handleResize() {
                    %s(window.innerWidth, window.innerHeight);
                }

                // Fire initial resize event when the component mounts.
                handleResize();

                // Add the event listener with cleanup.
                window.addEventListener("resize", handleResize);
                return () => window.removeEventListener("resize", handleResize);
            }, []);""" % (
                on_resize,
            )
        ]

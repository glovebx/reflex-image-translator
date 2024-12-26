import reflex as rx
from app.state import State
from .form_field import form_field


def add_auth_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("users", size=26),
                # rx.text("Sign in", size="4", display=["none", "none", "block"]),
                size="3",
                on_click=State.open_auth_dialog
            ),
        ),
        rx.dialog.content(
            rx.hstack(
                rx.badge(
                    rx.icon(tag="users", size=34),
                    color_scheme="grass",
                    radius="full",
                    padding="0.65rem",
                ),
                rx.vstack(
                    rx.dialog.title(
                        "Sign in",
                        weight="bold",
                        margin="0",
                    ),
                    # rx.dialog.description(
                    #     "Fill the form with the customer's info",
                    # ),
                    spacing="1",
                    height="100%",
                    align_items="start",
                ),
                height="100%",
                spacing="4",
                margin_bottom="1.5em",
                align_items="center",
                width="100%",
            ),
            rx.flex(
                rx.form.root(
                    rx.flex(
                        # # Name
                        form_field(
                            "Username",
                            "Login Name",
                            "text",
                            "name",
                            "user",
                        ),
                        # # Email
                        # form_field(
                        #     "Email", "user@reflex.dev", "email", "email", "mail"
                        # ),
                        # Password
                        form_field("Password", "", "password", "password", "square-asterisk"),

                        direction="column",
                        spacing="3",
                    ),
                    rx.cond(
                        State.login_message != "",
                        rx.box(
                            rx.text(State.login_message, color="red"),
                            padding="2",
                            margin_top="2",
                        ),
                    ),   
                    rx.flex(
                        # rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                                on_click=State.close_auth_dialog, 
                            ),
                        # ),
                        rx.form.submit(
                            # rx.dialog.close(
                                rx.button("Sign in", disabled=State.login_processing),
                            # ),
                            as_child=True,
                        ),
                        padding_top="2em",
                        spacing="3",
                        mt="4",
                        justify="end",
                    ),                  
                    on_submit=State.sign_in,
                    reset_on_submit=False,
                ),
                width="100%",
                direction="column",
                spacing="4",
            ),
            rx.center(
                rx.vstack(
                    rx.image(
                        src="/wechat.jpeg",  # 替换成你的图片路径
                        width="128px", # 限制宽度
                        height="auto", # 高度自动，保持比例
                        alt="scan to get login info", # 添加alt文本，增强可访问性
                        style={ "display": "block"} # 解决图片下方可能出现的空白间隙
                    ),
                    rx.text("微信扫码添加客服，获取登录信息"), # 添加文字，并设置上边距
                    spacing="1", # vstack内部元素间距
                    align="center",
                    class_name="py-4"                    
                ),
            ),
            max_width="450px",
            padding="1.5em",
            border=f"2px solid {rx.color('accent', 7)}",
            border_radius="25px",
        ),
        open=State.show_auth_dialog, 
        on_open_change=State.on_auth_mount,
    )

def add_profile_button() -> rx.Component:

    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.icon("circle-user", size=26),
                rx.text(State.current_user['nickname'], size="4", display=["none", "none", "block"]),
                size="3",
                color_scheme="gray"
            ),
        ),
        rx.popover.content(
            rx.box(
                rx.button(
                    "Logout",
                    variant="soft",
                    color_scheme="gray",
                    on_click=State.sign_out, 
                ),
                class_name="flex flex-col gap-8 border-slate-5 bg-slate-1 shadow-lg px-[0.875rem] py-4 border border-box rounded-xl overflow-hidden",
            ),
            side="top",
            align="center",
            avoid_collisions=True,
            class_name="items-center bg-transparent !shadow-none !p-0 border-none w-[254px] overflow-visible",
            font_family="var(--font-family)"
        ),
    )    
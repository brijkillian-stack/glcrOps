"""
apps/glcr/pages/unlock.py — Site PIN unlock screen (Path C).

Single public route besides /health. Renders the PIN form and routes
verify_pin() through AuthState. Sized for iPhone-thumb and iPad-Pencil
both. Numeric keyboard via inputmode=numeric. Scribble works because
the input is a stock <input>.
"""

import reflex as rx

from shared.auth import AuthState


def unlock_page() -> rx.Component:
    return rx.el.main(
        rx.el.div(
            # Brand mark
            rx.el.div(
                rx.el.div(class_name="unlock-brand-mark"),
                rx.el.h1("Graves Ops", class_name="unlock-title"),
                class_name="unlock-brand",
            ),

            # Form
            rx.el.form(
                rx.el.div(
                    rx.el.label("PIN", html_for="pin-input", class_name="unlock-label"),
                    rx.el.input(
                        id="pin-input",
                        type="tel",
                        inputmode="numeric",
                        pattern="[0-9]*",
                        autocomplete="one-time-code",
                        autofocus=True,
                        max_length=6,
                        value=AuthState.pin_input,
                        on_change=AuthState.set_pin_input,
                        class_name="unlock-input",
                        placeholder="• • • • • •",
                        aria_label="Site PIN",
                    ),
                    class_name="unlock-field",
                ),

                # Remember toggle (default on)
                rx.el.label(
                    rx.el.input(
                        type="checkbox",
                        checked=AuthState.remember_device,
                        on_change=AuthState.toggle_remember_device,
                        class_name="unlock-checkbox",
                    ),
                    rx.el.span("Remember this device for a year"),
                    class_name="unlock-remember",
                ),

                # Error slot
                rx.cond(
                    AuthState.error != "",
                    rx.el.div(AuthState.error, class_name="unlock-error", role="alert"),
                ),

                # Submit
                rx.el.button(
                    rx.cond(AuthState.is_loading, "Unlocking…", "Unlock"),
                    type="submit",
                    class_name="unlock-submit",
                    disabled=AuthState.is_loading,
                ),
                on_submit=AuthState.verify_pin,
                class_name="unlock-form",
            ),

            class_name="unlock-card",
        ),
        class_name="unlock-page",
    )

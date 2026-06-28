"""Brand identity visual panel — colors, fonts, logo."""

import html
import os

import streamlit as st

from knowledge_base.brand_identity import ensure_logo_extracted, get_visual_system


def render_brand_identity_panel() -> dict:
    """Render brand identity key components. Returns visual system dict."""
    visual = get_visual_system()

    st.markdown(
        '<div class="section-card"><div class="section-card-header">🎨 Brand Identity</div></div>',
        unsafe_allow_html=True,
    )

    col_logo, col_details = st.columns([1, 2])

    with col_logo:
        logo_path = ensure_logo_extracted()
        if os.path.exists(logo_path):
            st.image(logo_path, caption="Official logo", width='stretch')
        else:
            st.markdown(
                '<div class="logo-placeholder">B</div>',
                unsafe_allow_html=True,
            )
        st.caption(visual["logo"]["description"])

    with col_details:
        typo = visual["typography"]
        top_identity_values = (
            ("Essence", visual["essence"]),
            ("UI style", visual["ui_style"]),
            ("Typography", f"{typo['primary']} ({typo['style']})"),
        )
        identity_grid = '<div class="brand-identity-grid">'
        for label, value in top_identity_values:
            identity_grid += f"""
            <div class="brand-identity-box">
                <div class="brand-identity-label">{html.escape(label)}</div>
                <div class="brand-identity-value">{html.escape(str(value))}</div>
            </div>
            """
        identity_grid += "</div>"
        st.markdown(identity_grid, unsafe_allow_html=True)

        st.markdown("**Colors**")
        swatches = '<div class="color-swatches">'
        for color in visual["colors"]:
            swatches += f"""
            <div class="color-swatch" title="{html.escape(color['name'])}">
                <div class="color-chip" style="background:{color['hex']}"></div>
                <div class="color-meta">
                    <span class="color-name">{html.escape(color['name'])}</span>
                    <span class="color-hex">{color['hex']}</span>
                </div>
            </div>
            """
        swatches += "</div>"
        st.markdown(swatches, unsafe_allow_html=True)

        st.markdown(
            f"""
            **Fallback fonts:** {html.escape(', '.join(typo['fallback']))}
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="font-sample" style="font-family:Poppins, sans-serif;">'
            f"Beam Data — enterprise AI with confidence</p>",
            unsafe_allow_html=True,
        )

        st.caption(f"Avoid: {visual['avoid']}")

    return visual

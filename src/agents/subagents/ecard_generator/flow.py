"""eCard session flow — draft, refine, select, save."""

import logging

from src.agents.orchestrator.gift_session import parse_gift_session_reply
from src.agents.orchestrator.tools import load_recipient_context
from src.agents.subagents.ecard_generator.backgrounds import (
    backgrounds_as_images,
    generate_backgrounds_for_variants,
    is_dalle_enabled,
)
from src.agents.subagents.ecard_generator.parser import parse_ecard_request
from src.agents.subagents.ecard_generator.pipeline import draft_ecard_variants
from src.agents.subagents.ecard_generator.prompts import ECARD_REFINEMENT_FOOTER
from src.agents.subagents.ecard_generator.render import (
    render_final_card,
    render_preview_sheet,
)
from src.agents.subagents.ecard_generator.visual_hints import extract_visual_hints
from src.langchain_core.observability import trace_agent
from src.shared.conversation_context import AgentResponse, SlackContext, SlackFile
from src.shared.ecard_session_store import EcardSession, get_ecard_session_store
from src.storage.gift_history.store import get_gift_history_store
from src.storage.models.ecard_request import EcardRequest
from src.tools.vector_db.profile_store import get_profile_store

logger = logging.getLogger("gift_assistant.ecard_generator")


def _profile_chunks(recipient: str, occasion: str | None) -> list[str]:
    query = f"greeting card message for {recipient}"
    if occasion:
        query += f" {occasion}"
    return get_profile_store().query_profile(recipient, query=query)


def _combined_feedback(session: EcardSession, new_feedback: str | None) -> str | None:
    parts = list(session.feedback)
    if new_feedback and new_feedback.strip():
        parts.append(new_feedback.strip())
    return "\n".join(parts) if parts else None


def _format_variants_markdown(variants: list[dict], iteration: int) -> str:
    lines = []
    for i, card in enumerate(variants, start=1):
        style = card.get("style", "heartfelt").title()
        lines.append(
            f"*{i}. {card['headline']}* ({style})\n"
            f"{card['message']}\n"
            f"_{card.get('sign_off', 'Best wishes,')}_"
        )
    iter_label = f" — round {iteration}" if iteration > 1 else ""
    header = f"*eCard options{iter_label}:*\n\n"
    return header + "\n\n".join(lines)


def _build_visual_files(
    variants: list[dict],
    *,
    recipient: str,
    occasion: str | None,
    visual_hints: list[str],
    iteration: int,
    background_paths: dict[str, str],
) -> list[SlackFile]:
    backgrounds = backgrounds_as_images(background_paths)
    sheet_bytes = render_preview_sheet(
        variants,
        recipient=recipient,
        occasion=occasion,
        visual_hints=visual_hints,
        backgrounds=backgrounds or None,
    )
    iter_suffix = f"_round{iteration}" if iteration > 1 else ""
    art_note = " with DALL-E art" if backgrounds else ""
    return [
        SlackFile(
            data=sheet_bytes,
            filename=f"ecard_previews{iter_suffix}.jpg",
            title=f"eCard previews for {recipient}",
            initial_comment=(
                f"Preview all 3 designs{art_note}. Reply *1*, *2*, or *3* for a full-size "
                "downloadable card (GIF or JPEG) · feedback to refine backgrounds or text."
            ),
        )
    ]


def _build_response(
    request: EcardRequest,
    variants: list[dict],
    profile_text: str,
    iteration: int,
    visual_hints: list[str],
    background_paths: dict[str, str],
) -> AgentResponse:
    label = request.summary()
    variants_md = _format_variants_markdown(variants, iteration)
    dalle_line = ""
    if is_dalle_enabled():
        count = len(background_paths)
        if count:
            dalle_line = f"\n\n🖼️ *DALL-E backgrounds:* {count}/3 styles rendered and attached."
        else:
            dalle_line = "\n\n_Using gradient backgrounds (DALL-E unavailable — check OPENAI_API_KEY)._"

    text = (
        f"eCards for *{request.recipient}*"
        f"{f' — {request.occasion}' if request.occasion else ''}\n\n"
        f"*Profile context:*\n{profile_text}\n\n"
        f"{variants_md}"
        f"{dalle_line}\n\n"
        "_Preview JPEG attached — pick *1*/*2*/*3* for a full-size downloadable GIF/JPEG "
        "you can save from Slack and send on WhatsApp._"
        f"{ECARD_REFINEMENT_FOOTER}"
    )
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"eCards for {label}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Profile context:*\n{profile_text}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": variants_md},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "🎨 *Preview attached* — tap the JPEG/GIF file in Slack to download.\n"
                    "Reply *1*, *2*, or *3* for the final WhatsApp-ready card · "
                    "feedback to refine art/text (e.g. *more pink*, *new background*) · *done*"
                ),
            },
        },
    ]
    files = _build_visual_files(
        variants,
        recipient=request.recipient,
        occasion=request.occasion,
        visual_hints=visual_hints,
        iteration=iteration,
        background_paths=background_paths,
    )
    return AgentResponse(text=text, blocks=blocks, files=files)


def run_ecard_draft(
    request: EcardRequest,
    *,
    user_id: str,
    feedback: str | None = None,
    session: EcardSession | None = None,
    iteration: int = 1,
    visual_hints: list[str] | None = None,
    force_backgrounds: bool = False,
) -> tuple[AgentResponse, list[dict], list[str], dict[str, str]]:
    ctx = load_recipient_context(request.recipient)
    past_ecards = get_gift_history_store().get_ecard_history(request.recipient)
    chunks = _profile_chunks(request.recipient, request.occasion)

    combined = _combined_feedback(session, feedback) if session else feedback
    hints = list(visual_hints or (session.visual_hints if session else []))
    if feedback:
        hints = extract_visual_hints(feedback, hints)

    variants = draft_ecard_variants(
        request,
        chunks,
        ctx,
        past_ecards=past_ecards,
        feedback=combined,
        iteration=iteration,
    )

    background_paths = generate_backgrounds_for_variants(
        variants,
        user_id=user_id,
        recipient=request.recipient,
        occasion=request.occasion,
        visual_hints=hints,
        iteration=iteration,
        force_refresh=force_backgrounds or bool(feedback),
    )

    profile_text = (
        "\n".join(f"• {c}" for c in chunks)
        if chunks
        else "_No profile saved — card will be more general._"
    )
    if ctx.age_range:
        profile_text = f"*Age range:* {ctx.age_range}\n{profile_text}"

    response = _build_response(
        request, variants, profile_text, iteration, hints, background_paths
    )
    return response, variants, hints, background_paths


@trace_agent("ecard_generator.session")
def handle_active_ecard_session(
    message: str, session: EcardSession, context: SlackContext
) -> AgentResponse:
    action, index = parse_gift_session_reply(message)
    store = get_ecard_session_store()

    if action == "done":
        store.clear(context.user_id)
        return AgentResponse(
            text=f"eCard session for *{session.recipient}* ended."
        )

    if action == "select":
        if index is None or index >= len(session.last_variants):
            return AgentResponse(text="Please pick *1*, *2*, or *3* from the cards above.")
        card = session.last_variants[index]
        get_gift_history_store().save_ecard(
            session.recipient,
            card.get("style", "heartfelt"),
            card.get("headline", ""),
            card.get("message", ""),
            sign_off=card.get("sign_off"),
            occasion=session.occasion,
        )
        store.clear(context.user_id)
        logger.info(
            "eCard saved recipient=%s style=%s headline=%r",
            session.recipient,
            card.get("style"),
            card.get("headline"),
        )

        backgrounds = backgrounds_as_images(session.backgrounds)
        final = render_final_card(
            card,
            recipient=session.recipient,
            occasion=session.occasion,
            visual_hints=session.visual_hints,
            backgrounds=backgrounds or None,
        )
        ext = "GIF" if final.mime_type == "image/gif" else "JPEG"
        return AgentResponse(
            text=(
                f"*Final eCard ready for {session.recipient}!*\n\n"
                f"*{card['headline']}*\n"
                f"{card['message']}\n\n"
                f"_{card.get('sign_off', 'Best wishes,')}_\n\n"
                f"📎 Download the attached *{ext}* from Slack → share on WhatsApp."
            ),
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Final eCard for {session.recipient}* "
                            f"({card.get('style', '').title()})\n\n"
                            f"*{card['headline']}*\n"
                            f"{card['message']}\n\n"
                            f"_{card.get('sign_off', 'Best wishes,')}_\n\n"
                            f"📎 *Tap the {ext} file below to download* → forward on WhatsApp."
                        ),
                    },
                }
            ],
            files=[
                SlackFile(
                    data=final.data,
                    filename=final.filename,
                    title=final.title,
                    initial_comment=(
                        f"Your final eCard for *{session.recipient}* — "
                        "tap ⋮ → *Download* in Slack, then send on WhatsApp."
                    ),
                )
            ],
        )

    hints = extract_visual_hints(message, session.visual_hints)
    request = EcardRequest(
        recipient=session.recipient,
        occasion=session.occasion,
        raw_message=message,
    )
    response, variants, hints, bg_paths = run_ecard_draft(
        request,
        user_id=context.user_id,
        feedback=message,
        session=session,
        iteration=session.iteration + 1,
        visual_hints=hints,
        force_backgrounds=True,
    )
    store.update_after_iteration(
        context.user_id,
        message,
        variants,
        visual_hints=hints,
        backgrounds=bg_paths,
    )
    return response


def start_ecard_session(message: str, context: SlackContext) -> AgentResponse:
    parsed = parse_ecard_request(message)
    if not parsed or not parsed.get("recipient"):
        return AgentResponse(
            text=(
                "Tell me who the card is for, e.g.\n"
                "*create a greeting card for Mom for her birthday*"
            )
        )

    request = EcardRequest(
        recipient=parsed["recipient"],
        occasion=parsed.get("occasion"),
        raw_message=message,
    )

    if is_dalle_enabled():
        notice = AgentResponse(
            text=(
                f"Creating eCards for *{request.recipient}* with DALL-E background art — "
                "this may take up to a minute…"
            )
        )
    else:
        notice = None

    response, variants, hints, bg_paths = run_ecard_draft(
        request,
        user_id=context.user_id,
        iteration=1,
    )
    if variants:
        get_ecard_session_store().start(
            context.user_id,
            request.recipient,
            request.occasion,
            variants,
            visual_hints=hints,
            backgrounds=bg_paths,
        )

    if notice and is_dalle_enabled() and bg_paths:
        response.text = notice.text + "\n\n" + response.text

    return response

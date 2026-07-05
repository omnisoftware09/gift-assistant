"""eCard session flow — pick design, then refine, then finalize."""

import logging

from src.agents.orchestrator.tools import load_recipient_context
from src.agents.subagents.ecard_generator.backgrounds import (
    backgrounds_as_images,
    generate_background_for_style,
    generate_backgrounds_for_variants,
    get_background_provider,
    is_dalle_enabled,
    load_background,
)
from src.agents.subagents.ecard_generator.parser import parse_ecard_request
from src.agents.subagents.ecard_generator.pipeline import draft_ecard_variants, refine_ecard_variant
from src.agents.subagents.ecard_generator.prompts import ECARD_PICK_FOOTER, ECARD_REFINE_FOOTER
from src.agents.subagents.ecard_generator.render import (
    render_card_jpeg,
    render_final_card,
    render_preview_sheet,
)
from src.agents.subagents.ecard_generator.session import parse_pick_phase_reply, parse_refine_phase_reply
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
    try:
        return get_profile_store().query_profile(recipient, query=query)
    except Exception:
        logger.warning(
            "Profile lookup failed for %s — continuing without profile",
            recipient,
            exc_info=True,
        )
        return []


def _format_variants_markdown(variants: list[dict]) -> str:
    lines = []
    for i, card in enumerate(variants, start=1):
        style = card.get("style", "heartfelt").title()
        lines.append(
            f"*{i}. {card['headline']}* ({style})\n"
            f"{card['message']}\n"
            f"_{card.get('sign_off', 'Best wishes,')}_"
        )
    return "\n\n".join(lines)


def _format_card_markdown(card: dict, *, label: str | None = None) -> str:
    prefix = f"*{label}*\n" if label else ""
    return (
        f"{prefix}"
        f"*{card['headline']}* ({card.get('style', '').title()})\n"
        f"{card['message']}\n"
        f"_{card.get('sign_off', 'Best wishes,')}_"
    )


def _pick_response(
    request: EcardRequest,
    variants: list[dict],
    profile_text: str,
    background_paths: dict[str, str],
    visual_hints: list[str],
) -> AgentResponse:
    variants_md = _format_variants_markdown(variants)
    art_line = ""
    if is_dalle_enabled() and background_paths:
        art_line = f"\n\n🖼️ *AI backgrounds:* {len(background_paths)}/3 attached in preview."
    elif get_background_provider() == "pillow":
        art_line = "\n\n🎨 *Backgrounds:* Pillow gradients (set `ECARD_BACKGROUND_PROVIDER=openai` for AI art)."

    text = (
        f"eCards for *{request.recipient}*"
        f"{f' — {request.occasion}' if request.occasion else ''}\n\n"
        f"*Profile context:*\n{profile_text}\n\n"
        f"*Step 1 — pick a design:*\n\n{variants_md}"
        f"{art_line}\n\n"
        "_Choose *1*, *2*, or *3* below — then you'll refine that design before downloading._"
        f"{ECARD_PICK_FOOTER}"
    )
    backgrounds = backgrounds_as_images(background_paths)
    sheet = render_preview_sheet(
        variants,
        recipient=request.recipient,
        occasion=request.occasion,
        visual_hints=visual_hints,
        backgrounds=backgrounds or None,
    )
    return AgentResponse(
        text=text,
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Step 1: Pick a design for {request.recipient}"},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": variants_md}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "🎨 *Preview attached* — reply *1*, *2*, or *3* to select a design.\n"
                        "You'll refine that design in step 2 before downloading."
                    ),
                },
            },
        ],
        files=[
            SlackFile(
                data=sheet,
                filename="ecard_design_picks.jpg",
                title=f"Design options for {request.recipient}",
                initial_comment="Pick a design: reply *1*, *2*, or *3* in chat.",
            )
        ],
    )


def _refine_response(
    session: EcardSession,
    card: dict,
    *,
    round_label: str,
    background_path: str | None,
) -> AgentResponse:
    idx = (session.selected_index or 0) + 1
    style = card.get("style", "").title()
    card_md = _format_card_markdown(card, label=f"Design {idx} — {style}")

    feedback_summary = ""
    if session.design_feedback:
        feedback_summary = "\n\n*Your refinements so far:*\n" + "\n".join(
            f"• {f}" for f in session.design_feedback
        )

    text = (
        f"*Step 2 — refine design {idx}* ({style})\n\n"
        f"{card_md}"
        f"{feedback_summary}\n\n"
        "_Describe changes for THIS design only "
        "(e.g. *add a cartoon girl with grad cap*) · "
        "*finalize* when ready to download · *done* to cancel · "
        "*pick 2* to switch designs_"
        f"{ECARD_REFINE_FOOTER}"
    )

    bg_image = load_background(background_path) if background_path else None
    backgrounds = {card.get("style", "heartfelt"): bg_image} if bg_image else None
    preview = render_card_jpeg(
        card,
        recipient=session.recipient,
        occasion=session.occasion,
        visual_hints=session.visual_hints,
        backgrounds=backgrounds,
    )

    return AgentResponse(
        text=text,
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Step 2: Refine design {idx}"},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": card_md + feedback_summary}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🎨 *Current preview attached* ({round_label})\n"
                        "Tell me what to change · *finalize* to download · *pick 1/2/3* to switch"
                    ),
                },
            },
        ],
        files=[
            SlackFile(
                data=preview,
                filename=f"ecard_design_{idx}_preview.jpg",
                title=f"Design {idx} preview",
                initial_comment=(
                    f"Refining design *{idx}* — describe changes or say *finalize* to download."
                ),
            )
        ],
    )


def _finalize_response(session: EcardSession, card: dict) -> AgentResponse:
    get_gift_history_store().save_ecard(
        session.recipient,
        card.get("style", "heartfelt"),
        card.get("headline", ""),
        card.get("message", ""),
        sign_off=card.get("sign_off"),
        occasion=session.occasion,
    )
    logger.info(
        "eCard finalized recipient=%s style=%s headline=%r",
        session.recipient,
        card.get("style"),
        card.get("headline"),
    )

    bg_image = load_background(session.selected_background) if session.selected_background else None
    backgrounds = {card.get("style", "heartfelt"): bg_image} if bg_image else None
    final = render_final_card(
        card,
        recipient=session.recipient,
        occasion=session.occasion,
        visual_hints=session.visual_hints,
        backgrounds=backgrounds,
    )
    ext = "GIF" if final.mime_type == "image/gif" else "JPEG"
    return AgentResponse(
        text=(
            f"*Final eCard ready for {session.recipient}!*\n\n"
            f"*{card['headline']}*\n{card['message']}\n\n"
            f"_{card.get('sign_off', 'Best wishes,')}_\n\n"
            f"📎 Download the *{ext}* below → share on WhatsApp."
        ),
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Final eCard for {session.recipient}*\n\n"
                        f"*{card['headline']}*\n{card['message']}\n\n"
                        f"📎 *Tap the {ext} file to download*"
                    ),
                },
            }
        ],
        files=[
            SlackFile(
                data=final.data,
                filename=final.filename,
                title=final.title,
                initial_comment="Final card — tap ⋮ → Download, then send on WhatsApp.",
            )
        ],
    )


def run_initial_draft(
    request: EcardRequest,
    *,
    user_id: str,
) -> tuple[AgentResponse, list[dict], list[str], dict[str, str]]:
    ctx = load_recipient_context(request.recipient)
    past_ecards = get_gift_history_store().get_ecard_history(request.recipient)
    chunks = _profile_chunks(request.recipient, request.occasion)

    variants = draft_ecard_variants(
        request, chunks, ctx, past_ecards=past_ecards, iteration=1
    )
    background_paths = generate_backgrounds_for_variants(
        variants,
        user_id=user_id,
        recipient=request.recipient,
        occasion=request.occasion,
        visual_hints=[],
        iteration=1,
    )

    profile_text = (
        "\n".join(f"• {c}" for c in chunks)
        if chunks
        else "_No profile saved — card will be more general._"
    )
    if ctx.age_range:
        profile_text = f"*Age range:* {ctx.age_range}\n{profile_text}"

    response = _pick_response(request, variants, profile_text, background_paths, [])
    return response, variants, [], background_paths


def _background_for_selection(session: EcardSession, card: dict) -> str | None:
    style = card.get("style", "heartfelt")
    if session.backgrounds.get(style):
        return session.backgrounds[style]
    return generate_background_for_style(
        style,
        user_id=session.user_id,
        recipient=session.recipient,
        occasion=session.occasion,
        visual_hints=session.visual_hints,
        design_feedback=session.design_feedback,
        iteration=session.refine_round,
    )


def _enter_refine_phase(
    session: EcardSession,
    index: int,
    *,
    initial_feedback: str | None = None,
    context: SlackContext,
) -> AgentResponse:
    store = get_ecard_session_store()
    card = dict(session.last_variants[index])
    bg_path = _background_for_selection(session, card)

    store.select_design(
        context.user_id,
        index,
        card,
        initial_feedback=initial_feedback,
        background_path=bg_path,
    )
    session = store.get(context.user_id)
    assert session is not None

    if initial_feedback:
        return _run_refinement(initial_feedback, session, context)

    round_label = "starting point"
    return _refine_response(session, card, round_label=round_label, background_path=bg_path)


def _run_refinement(
    feedback: str,
    session: EcardSession,
    context: SlackContext,
) -> AgentResponse:
    store = get_ecard_session_store()
    card = dict(session.selected_card or {})
    request = EcardRequest(
        recipient=session.recipient,
        occasion=session.occasion,
        raw_message=feedback,
    )
    chunks = _profile_chunks(session.recipient, session.occasion)
    hints = extract_visual_hints(feedback, session.visual_hints)

    refined = refine_ecard_variant(
        card,
        request,
        chunks,
        feedback=feedback,
        prior_feedback=session.design_feedback,
    )

    design_feedback = list(session.design_feedback) + [feedback]
    bg_path = generate_background_for_style(
        refined.get("style", "heartfelt"),
        user_id=context.user_id,
        recipient=session.recipient,
        occasion=session.occasion,
        visual_hints=hints,
        design_feedback=design_feedback,
        iteration=session.refine_round + 1,
        force_refresh=True,
    ) or session.selected_background

    store.update_after_refinement(
        context.user_id,
        feedback,
        refined,
        background_path=bg_path,
        visual_hints=hints,
    )
    session = store.get(context.user_id)
    assert session is not None

    return _refine_response(
        session,
        refined,
        round_label=f"round {session.refine_round}",
        background_path=bg_path,
    )


@trace_agent("ecard_generator.session")
def handle_active_ecard_session(
    message: str, session: EcardSession, context: SlackContext
) -> AgentResponse:
    store = get_ecard_session_store()

    if session.phase == "refine":
        return _handle_refine_phase(message, session, context)

    return _handle_pick_phase(message, session, context)


def _handle_pick_phase(
    message: str, session: EcardSession, context: SlackContext
) -> AgentResponse:
    store = get_ecard_session_store()
    action, index, trailing = parse_pick_phase_reply(message)

    if action == "done":
        store.clear(context.user_id)
        return AgentResponse(text="eCard session cancelled.")

    if action == "select" and index is not None:
        if index >= len(session.last_variants):
            return AgentResponse(text="Please pick *1*, *2*, or *3* from the designs above.")
        return _enter_refine_phase(
            session,
            index,
            initial_feedback=trailing,
            context=context,
        )

    return AgentResponse(
        text=(
            "*Step 1 — pick a design first.*\n\n"
            "Reply *1*, *2*, or *3* to choose a design.\n"
            "You can also say e.g. *design 2, add a cartoon girl with grad cap*.\n"
            "*done* to cancel."
        )
    )


def _handle_refine_phase(
    message: str, session: EcardSession, context: SlackContext
) -> AgentResponse:
    store = get_ecard_session_store()
    action, index, feedback = parse_refine_phase_reply(message)

    if action == "done":
        store.clear(context.user_id)
        return AgentResponse(text="eCard session cancelled — nothing saved.")

    if action == "finalize":
        card = session.selected_card
        if not card:
            return AgentResponse(text="No design selected. Start over with a new eCard request.")
        store.clear(context.user_id)
        return _finalize_response(session, card)

    if action == "switch" and index is not None:
        if index >= len(session.last_variants):
            return AgentResponse(text="Please pick *1*, *2*, or *3*.")
        store.return_to_pick(context.user_id)
        session = store.get(context.user_id)
        assert session is not None
        return _enter_refine_phase(session, index, context=context)

    if action == "feedback" and feedback:
        return _run_refinement(feedback, session, context)

    idx = (session.selected_index or 0) + 1
    return AgentResponse(
        text=(
            f"You're refining *design {idx}*.\n"
            "Describe what to change (e.g. *add a cartoon girl with grad cap*) · "
            "*finalize* to download · *done* to cancel"
        )
    )


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

    try:
        return _start_ecard_session_inner(request, context)
    except Exception as exc:
        logger.exception("eCard session failed recipient=%s", request.recipient)
        if _is_openai_quota_error(exc):
            return AgentResponse(
                text=(
                    "⚠️ *OpenAI quota exceeded.*\n\n"
                    "For free local testing, set in `.env` and restart the bot:\n"
                    "```\n"
                    "ECARD_BACKGROUND_PROVIDER=pillow\n"
                    "LLM_PROVIDER=ollama\n"
                    "EMBEDDING_PROVIDER=ollama\n"
                    "```\n"
                    "Remove or set `ECARD_DALLE_ENABLED=false` if present."
                )
            )
        return AgentResponse(
            text="Sorry, I couldn't create the eCard. Check the bot logs for details."
        )


def _is_openai_quota_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "insufficient_quota" in text or "rate limit" in text or type(exc).__name__ == "RateLimitError"


def _start_ecard_session_inner(request: EcardRequest, context: SlackContext) -> AgentResponse:
    preamble = ""
    if is_dalle_enabled():
        preamble = (
            f"Creating 3 designs for *{request.recipient}* with AI background art "
            "(may take a minute)…\n\n"
        )

    response, variants, hints, bg_paths = run_initial_draft(request, user_id=context.user_id)
    if variants:
        get_ecard_session_store().start(
            context.user_id,
            request.recipient,
            request.occasion,
            variants,
            visual_hints=hints,
            backgrounds=bg_paths,
        )

    if preamble:
        response.text = preamble + response.text

    return response

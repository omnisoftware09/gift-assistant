from slack_bolt import App

from src.agents.orchestrator.agent import handle_slash_command
from src.interfaces.slack.formatters.responses import format_response
from src.shared.conversation_context import SlackContext


def register_slash_commands(app: App) -> None:
    @app.command("/gift")
    def gift_command(ack, command, respond, logger):
        ack()
        context = _context_from_command(command)
        query = command.get("text", "").strip()
        try:
            response = handle_slash_command("gift", query, context)
            respond(**format_response(response))
        except Exception:
            logger.exception("Failed to handle /gift")
            respond(text="Sorry, something went wrong with /gift.")

    @app.command("/events")
    def events_command(ack, command, respond, logger):
        ack()
        context = _context_from_command(command)
        query = command.get("text", "").strip()
        try:
            response = handle_slash_command("events", query, context)
            respond(**format_response(response))
        except Exception:
            logger.exception("Failed to handle /events")
            respond(text="Sorry, something went wrong with /events.")

    @app.command("/check-alerts")
    def check_alerts_command(ack, command, respond, logger):
        ack()
        from src.workers.event_monitor_job import run_proactive_check

        try:
            result = run_proactive_check(app.client, command["user_id"])
            if result["sent"]:
                respond(text=f"Sent {result['sent']} proactive alert(s) to your DM.")
            else:
                respond(text=result.get("message", "No new alerts to send."))
        except Exception:
            logger.exception("Failed to handle /check-alerts")
            respond(text="Sorry, something went wrong checking alerts.")

    @app.command("/import-profiles")
    def import_profiles_command(ack, command, respond, logger):
        ack()
        from src.agents.subagents.profile_collector.import_handler import handle_profile_import

        context = _context_from_command(command)
        query = command.get("text", "").strip()
        try:
            from pathlib import Path

            path = Path(query).expanduser() if query else None
            response = handle_profile_import(path, context=context)
            respond(**format_response(response))
        except Exception:
            logger.exception("Failed to handle /import-profiles")
            respond(text="Sorry, something went wrong importing profiles.")


def _context_from_command(command) -> SlackContext:
    return SlackContext(
        user_id=command["user_id"],
        channel_id=command["channel_id"],
        thread_ts=None,
        team_id=command.get("team_id"),
    )

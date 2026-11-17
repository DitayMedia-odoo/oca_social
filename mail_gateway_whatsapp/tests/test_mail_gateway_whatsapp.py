# Copyright 2022 CreuBlanca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import copy
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from markupsafe import Markup

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, RecordCapturer
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.mail_gateway.tests.common import MailGatewayTestCase
from odoo.addons.mail_gateway_whatsapp.models.mail_gateway_whatsapp import (
    MailGatewayWhatsappService,
)


@tagged("-at_install", "post_install")
class TestMailGatewayWhatsApp(MailGatewayTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webhook = "demo_hook"
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "gateway",
                "gateway_type": "whatsapp",
                "token": "token",
                "whatsapp_security_key": "key",
                "webhook_secret": "MY-SECRET",
                "member_ids": [(4, cls.env.user.id)],
            }
        )
        cls.ws_template = cls.env["mail.whatsapp.template"].create(
            {
                "name": "New template",
                "category": "marketing",
                "language": "es",
                "body": "Demo template",
                "state": "approved",
                "is_supported": True,
                "gateway_id": cls.gateway.id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Partner", "phone": "+34 600 000 000"}
        )
        cls.password = "my_new_password"
        cls.message_01 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "34699999999",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "NAME"},
                                        "wa_id": "34699999999",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "34699999999",
                                        "id": "wamid.ID",
                                        "timestamp": "1234",
                                        "text": {"body": "MESSAGE_BODY"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        cls.message_02 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "1234",
                                },
                                "contacts": [
                                    {"profile": {"name": "NAME"}, "wa_id": "1234"}
                                ],
                                "messages": [
                                    {
                                        "from": "1234",
                                        "id": "wamid.ID",
                                        "timestamp": "1234",
                                        "type": "image",
                                        "image": {
                                            "caption": "CAPTION",
                                            "mime_type": "image/jpeg",
                                            "sha256": "IMAGE_HASH",
                                            "id": "12356",
                                        },
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        cls.audio_message = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "1234",
                                },
                                "contacts": [
                                    {"profile": {"name": "NAME"}, "wa_id": "1234"}
                                ],
                                "messages": [
                                    {
                                        "from": "1234",
                                        "id": "wamid.ID",
                                        "timestamp": "1234",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/oga",
                                            "sha256": "IMAGE_HASH",
                                            "id": "12356",
                                        },
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

    def test_webhook_management(self):
        self.gateway.webhook_key = self.webhook
        self.assertTrue(self.gateway.can_set_webhook)
        self.gateway.set_webhook()
        self.assertEqual(self.gateway.integrated_webhook_state, "pending")
        self.gateway.remove_webhook()
        self.assertFalse(self.gateway.integrated_webhook_state)
        self.gateway.set_webhook()
        self.assertEqual(self.gateway.integrated_webhook_state, "pending")
        self.url_open(
            "/gateway/{}/{}/update?hub.verify_token={}&hub.challenge={}".format(
                self.gateway.gateway_type,
                self.webhook,
                self.gateway.whatsapp_security_key + "12",
                "22",
            ),
        )
        self.assertEqual(self.gateway.integrated_webhook_state, "pending")
        self.integrate_webhook()
        self.assertEqual(self.gateway.integrated_webhook_state, "integrated")
        self.gateway.remove_webhook()
        self.assertFalse(self.gateway.integrated_webhook_state)

    def integrate_webhook(self):
        self.url_open(
            "/gateway/{}/{}/update?hub.verify_token={}&hub.challenge={}".format(
                self.gateway.gateway_type,
                self.webhook,
                self.gateway.whatsapp_security_key,
                "22",
            ),
        )

    def set_message(self, message, webhook, headers=True):
        data = json.dumps(message)
        headers_dict = {"Content-Type": "application/json"}
        if headers:
            hex_dig = hmac.new(
                self.gateway.webhook_secret.encode(),
                data.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers_dict["x-hub-signature-256"] = f"sha256={hex_dig}"
        return self.url_open(
            f"/gateway/{self.gateway.gateway_type}/{webhook}/update",
            data=data,
            headers=headers_dict,
        )

    def receive_message(self, message):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        self.set_message(message, self.webhook)
        chat = self.env["discuss.channel"].search(
            [("gateway_id", "=", self.gateway.id)]
        )
        self.assertTrue(chat)
        self.assertTrue(chat.message_ids)
        return chat.message_ids

    def test_receive_message_01(self):
        message = self.receive_message(self.message_01)
        self.assertFalse(message.author_id)
        self.assertFalse(message.parent_id)

    def _quick_reply_message(self, payload):
        """Build an inbound webhook payload carrying only a tapped reply."""
        message = {"from": "34699999999", "id": "wamid.QR", "timestamp": "1234"}
        message.update(payload)
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "34699999999",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "NAME"},
                                        "wa_id": "34699999999",
                                    }
                                ],
                                "messages": [message],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

    def test_receive_interactive_button_reply(self):
        # Tapping an interactive button must land in the conversation.
        message = self.receive_message(
            self._quick_reply_message(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "confirm-yes", "title": "Si, confirmo"},
                    },
                }
            )
        )
        self.assertIn("Si, confirmo", message.body)

    def test_receive_interactive_list_reply(self):
        message = self.receive_message(
            self._quick_reply_message(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "list_reply",
                        "list_reply": {
                            "id": "slot-2100",
                            "title": "21:00",
                            "description": "Terraza",
                        },
                    },
                }
            )
        )
        self.assertIn("21:00", message.body)
        self.assertIn("Terraza", message.body)

    def test_receive_template_button(self):
        message = self.receive_message(
            self._quick_reply_message(
                {
                    "type": "button",
                    "button": {"payload": "CONFIRM", "text": "Confirmar"},
                }
            )
        )
        self.assertIn("Confirmar", message.body)

    def test_receive_quick_reply_is_escaped(self):
        # The title comes from the template, but it is echoed back by the
        # sender, so it must not be able to inject markup.
        message = self.receive_message(
            self._quick_reply_message(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "x", "title": "<b>bold</b>"},
                    },
                }
            )
        )
        self.assertNotIn("<b>bold</b>", message.body)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", message.body)

    def test_receive_message_02(self):
        # Check that the partner is assigned automatically
        partner = self.env["res.partner"].create(
            {"name": "DEMO", "phone": "+34699999999"}
        )
        message = self.receive_message(self.message_01)
        self.assertEqual(message.author_id, partner)
        self.assertFalse(message.parent_id)

    def test_receive_related_message(self):
        """
        Send outgoing message, and then receive a reply message
        with reference to the original.
        """
        # Send outgoing
        partner = self.env["res.partner"].create(
            {"name": "DEMO", "phone": "+34699999999"}
        )
        ctx = {
            "default_res_model": partner._name,
            "default_res_id": partner.id,
            "default_number_field_name": "phone",
            "default_composition_mode": "comment",
            "default_gateway_id": self.gateway.id,
        }
        self.gateway.whatsapp_account_id = "123456"
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.body = "Body test"
        form_composer.template_id = self.ws_template
        composer = form_composer.save()
        channel = partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        ID_WHATSAPP = "wamid.TEST_UNIQUE_ID_123"
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post") as post_mock,
        ):
            response_mock = MagicMock()
            response_mock.status_code = 200
            # Mock the response of whatsapp to include an assigned ID
            response_mock.json.return_value = {"messages": [{"id": ID_WHATSAPP}]}
            post_mock.return_value = response_mock
            composer.action_send_whatsapp()
        message = capture.records
        # Check that the sent message notification contains the received Whatsapp ID
        self.assertTrue(
            message.notification_ids.filtered(
                lambda msg: msg.gateway_message_id == ID_WHATSAPP
            )
        )
        # Receive message 01 with related id set.
        reply_message = self.message_01
        reply_message["entry"][0]["changes"][0]["value"]["messages"][0]["context"] = {
            "id": ID_WHATSAPP
        }
        received_reply = self.receive_message(reply_message)
        self.assertEqual(message.id, received_reply.parent_id.id)

    def test_receive_message_03(self):
        class GetImageResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"url": "http://demo.url", "mime_type": "image/png"}

            content = b"binary_data"

        with patch("requests.get") as get_mock:
            get_mock.return_value = GetImageResponse()
            message = self.receive_message(self.message_02)
            self.assertEqual(message.body, "<p>CAPTION</p>")

    def test_receive_audio_message(self):
        class GetAudioResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"url": "http://demo.url", "mime_type": "audio/oga"}

            content = b"binary_data"

        with patch("requests.get") as get_mock:
            get_mock.return_value = GetAudioResponse()
            message = self.receive_message(self.audio_message)
            # Check that the attachment is marked as voice
            self.assertTrue(message.attachment_ids.voice_ids)

    @mute_logger("odoo.addons.mail_gateway.controllers.gateway")
    def test_post_no_signature_no_message(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        self.set_message(self.message_01, self.webhook, False)
        self.assertFalse(
            self.env["discuss.channel"].search([("gateway_id", "=", self.gateway.id)])
        )

    @mute_logger("odoo.addons.mail_gateway.controllers.gateway")
    def test_post_wrong_signature_no_message(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        data = json.dumps(self.message_01)
        hex_dig = hmac.new(
            self.gateway.webhook_secret.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "x-hub-signature-256": f"sha256=1234{hex_dig}",
        }
        self.url_open(
            f"/gateway/{self.gateway.gateway_type}/{self.webhook}/update",
            data=data,
            headers=headers,
        )
        self.assertFalse(
            self.env["discuss.channel"].search([("gateway_id", "=", self.gateway.id)])
        )

    def test_send_image(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        composer = self.env["whatsapp.composer"].create(
            {
                "res_model": self.partner._name,
                "res_id": self.partner.id,
                "number_field_name": "phone",
                "gateway_id": self.gateway.id,
            }
        )
        composer.action_view_whatsapp()
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", self.gateway.id)]
        )

        with patch("requests.post") as post_mock:
            post_mock.return_value = MagicMock()
            channel.message_post(
                attachments=[("demo.png", b"IMAGE")],
                subtype_xmlid="mail.mt_comment",
                message_type="comment",
            )
            post_mock.assert_called()
            self.assertEqual(post_mock.call_count, 2)

    def test_send_document_error(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        composer = self.env["whatsapp.composer"].create(
            {
                "res_model": self.partner._name,
                "res_id": self.partner.id,
                "number_field_name": "phone",
                "gateway_id": self.gateway.id,
            }
        )
        composer.action_view_whatsapp()
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", self.gateway.id)]
        )
        with mute_logger(
            "odoo.addons.mail_gateway_whatsapp.models.mail_gateway_whatsapp"
        ):
            message = channel.message_post(
                attachments=[("demo.xml", b"IMAGE")],
                subtype_xmlid="mail.mt_comment",
                message_type="comment",
            )
        self.assertEqual(message.notification_ids.notification_status, "exception")

    def test_send_message_text(self):
        """
        Test that the message is sent correctly
        - First message need a template
        - Second message does not need a template
        """
        ctx = {
            "default_res_model": self.partner._name,
            "default_res_id": self.partner.id,
            "default_number_field_name": "phone",
            "default_composition_mode": "comment",
            "default_gateway_id": self.gateway.id,
        }
        self.gateway.whatsapp_account_id = "123456"
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.body = "Body test"
        self.assertTrue(form_composer.is_required_template)
        self.assertTrue(form_composer._get_modifier("template_id", "required"))
        form_composer.template_id = self.ws_template
        composer = form_composer.save()
        self.assertEqual(composer.body, "Demo template")
        channel = self.partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post") as post_mock,
        ):
            post_mock.return_value = MagicMock()
            composer.action_send_whatsapp()
        self.assertEqual(len(capture.records), 1)
        self.assertEqual(capture.records.body, Markup("<p>Demo template</p>"))
        # second message
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.body = "Body test"
        self.assertFalse(form_composer.is_required_template)
        self.assertFalse(form_composer._get_modifier("template_id", "required"))
        composer = form_composer.save()
        self.assertEqual(composer.body, "Body test")
        channel = self.partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post") as post_mock,
        ):
            post_mock.return_value = MagicMock()
            composer.action_send_whatsapp()
        self.assertEqual(len(capture.records), 1)
        self.assertEqual(capture.records.body, Markup("<p>Body test</p>"))

    def _integrate(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()

    def _count_wamid(self, wamid):
        return self.env["mail.message"].search_count(
            [("message_id", "=", f"<{wamid}@whatsapp.mail_gateway>")]
        )

    def test_receive_duplicate_message_is_ignored(self):
        # Meta retries a delivery that is not answered in time: the same wamid
        # must end up as a single message in the conversation.
        self.receive_message(self.message_01)
        self.assertEqual(self._count_wamid("wamid.ID"), 1)
        response = self.set_message(self.message_01, self.webhook)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_wamid("wamid.ID"), 1)
        other = copy.deepcopy(self.message_01)
        other["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid.OTHER"
        self.set_message(other, self.webhook)
        self.assertEqual(self._count_wamid("wamid.OTHER"), 1)
        self.assertEqual(self._count_wamid("wamid.ID"), 1)

    @mute_logger("odoo.addons.mail_gateway_whatsapp.models.mail_gateway_whatsapp")
    def test_failing_message_does_not_break_webhook(self):
        self._integrate()
        payload = copy.deepcopy(self.message_01)
        value = payload["entry"][0]["changes"][0]["value"]
        bad_msg = value["messages"][0]
        bad_msg["id"] = "wamid.BAD"
        good_msg = copy.deepcopy(bad_msg)
        good_msg["id"] = "wamid.GOOD"
        good_msg["text"] = {"body": "GOOD BODY"}
        value["messages"] = [bad_msg, good_msg]
        original = MailGatewayWhatsappService._process_update

        def process_update(service, chat, message, value):
            if message["id"] == "wamid.BAD":
                raise ValueError("boom")
            return original(service, chat, message, value)

        with patch.object(
            MailGatewayWhatsappService, "_process_update", process_update
        ):
            response = self.set_message(payload, self.webhook)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_wamid("wamid.BAD"), 0)
        self.assertEqual(self._count_wamid("wamid.GOOD"), 1)

    @mute_logger("odoo.addons.mail_gateway.controllers.gateway")
    def test_invalid_json_answers_200(self):
        self._integrate()
        response = self.url_open(
            f"/gateway/{self.gateway.gateway_type}/{self.webhook}/update",
            data="{not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)

    def _status_payload(self, recipient, wamid, status, errors=None):
        status_info = {
            "id": wamid,
            "status": status,
            "timestamp": "1234",
            "recipient_id": recipient,
        }
        if errors is not None:
            status_info["errors"] = errors
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "1234",
                                },
                                "statuses": [status_info],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

    def _send_outgoing(self, wamid="wamid.OUT"):
        self._integrate()
        partner = self.env["res.partner"].create(
            {"name": "DEMO", "phone": "+34699999999"}
        )
        ctx = {
            "default_res_model": partner._name,
            "default_res_id": partner.id,
            "default_number_field_name": "phone",
            "default_composition_mode": "comment",
            "default_gateway_id": self.gateway.id,
        }
        self.gateway.whatsapp_account_id = "123456"
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.body = "Body test"
        form_composer.template_id = self.ws_template
        composer = form_composer.save()
        channel = partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        with patch("requests.post") as post_mock:
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.json.return_value = {"messages": [{"id": wamid}]}
            post_mock.return_value = response_mock
            composer.action_send_whatsapp()
        notifications = self.env["mail.notification"].search(
            [("gateway_message_id", "=", wamid)]
        )
        self.assertTrue(notifications)
        return channel, notifications

    def _send_status(self, channel, wamid, status, errors=None):
        payload = self._status_payload(
            channel.gateway_channel_token, wamid, status, errors
        )
        response = self.set_message(payload, self.webhook)
        self.assertEqual(response.status_code, 200)

    def _statuses(self, notifications):
        notifications.invalidate_recordset()
        return set(notifications.mapped("notification_status"))

    def test_status_delivered_then_read(self):
        channel, notifications = self._send_outgoing()
        self.assertEqual(self._statuses(notifications), {"pending"})
        self._send_status(channel, "wamid.OUT", "sent")
        self.assertEqual(self._statuses(notifications), {"pending"})
        self._send_status(channel, "wamid.OUT", "delivered")
        self.assertEqual(self._statuses(notifications), {"sent"})
        self.assertFalse(any(notifications.mapped("is_read")))
        self._send_status(channel, "wamid.OUT", "read")
        self.assertEqual(self._statuses(notifications), {"sent"})
        self.assertTrue(all(notifications.mapped("is_read")))
        self.assertTrue(all(notifications.mapped("read_date")))

    def test_status_out_of_order_never_goes_back(self):
        channel, notifications = self._send_outgoing()
        # "read" arrives before "delivered"
        self._send_status(channel, "wamid.OUT", "read")
        self._send_status(channel, "wamid.OUT", "delivered")
        self.assertEqual(self._statuses(notifications), {"sent"})
        self.assertTrue(all(notifications.mapped("is_read")))

    def test_status_failed_without_error_data(self):
        # Meta does not always include error_data.details in a failed status.
        channel, notifications = self._send_outgoing()
        self._send_status(
            channel,
            "wamid.OUT",
            "failed",
            errors=[{"code": 131047, "title": "Re-engagement message"}],
        )
        self.assertEqual(self._statuses(notifications), {"exception"})
        for notification in notifications:
            self.assertIn("[131047] Re-engagement message", notification.failure_reason)

    def test_status_failed_with_error_data(self):
        channel, notifications = self._send_outgoing()
        self._send_status(
            channel,
            "wamid.OUT",
            "failed",
            errors=[{"code": 131047, "error_data": {"details": "Window closed"}}],
        )
        notifications.invalidate_recordset()
        for notification in notifications:
            self.assertIn("[131047] Window closed", notification.failure_reason)

    def test_status_of_unknown_message_is_ignored(self):
        channel, notifications = self._send_outgoing()
        self._send_status(channel, "wamid.UNKNOWN", "delivered")
        self.assertEqual(self._statuses(notifications), {"pending"})

    def test_compose(self):
        self.gateway.webhook_key = self.webhook
        self.gateway.set_webhook()
        self.integrate_webhook()
        composer = self.env["whatsapp.composer"].create(
            {
                "res_model": self.partner._name,
                "res_id": self.partner.id,
                "number_field_name": "phone",
                "gateway_id": self.gateway.id,
            }
        )
        composer.action_view_whatsapp()
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", self.gateway.id)]
        )
        self.assertTrue(channel)
        self.assertFalse(channel.message_ids)
        with self.assertRaises(UserError):
            composer.action_send_whatsapp()
        composer.body = "DEMO"
        with patch("requests.post") as post_mock:
            post_mock.return_value = MagicMock()
            composer.action_send_whatsapp()
            post_mock.assert_called()
        channel.invalidate_recordset()
        self.assertTrue(channel.message_ids)

    def test_send_message_with_variable(self):
        ctx = {
            "default_res_model": self.partner._name,
            "default_res_id": self.partner.id,
            "default_number_field_name": "phone",
            "default_composition_mode": "comment",
            "default_gateway_id": self.gateway.id,
        }
        tmpl_with_vars = self.env["mail.whatsapp.template"].create(
            {
                "name": "Partner Vars",
                "category": "utility",
                "language": "es",
                "header": "Hi {{1}}",
                "body": "Name: {{1}} · Tel: {{2}}",
                "gateway_id": self.gateway.id,
                "variable_ids": [Command.clear()],
                "state": "approved",
                "is_supported": True,
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        self.env["mail.whatsapp.template.variable"].create(
            {
                "name": "{{1}}",
                "line_type": "header",
                "template_id": tmpl_with_vars.id,
                "field_name": "name",
            }
        )
        self.env["mail.whatsapp.template.variable"].create(
            {
                "name": "{{1}}",
                "line_type": "body",
                "template_id": tmpl_with_vars.id,
                "field_name": "name",
            }
        )
        self.env["mail.whatsapp.template.variable"].create(
            {
                "name": "{{2}}",
                "line_type": "body",
                "template_id": tmpl_with_vars.id,
                "field_name": "phone",
            }
        )
        self.env["mail.whatsapp.template.button"].create(
            {
                "name": "mobile",
                "button_type": "phone_number",
                "template_id": tmpl_with_vars.id,
                "call_number": "+34666555444",
            }
        )
        self.assertEqual(len(tmpl_with_vars.variable_ids), 3)
        self.assertEqual(len(tmpl_with_vars.button_ids), 1)
        self.gateway.whatsapp_account_id = "123456"
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.template_id = tmpl_with_vars
        self.assertTrue(form_composer.is_required_template)
        self.assertTrue(form_composer._get_modifier("template_id", "required"))
        composer = form_composer.save()
        channel = self.partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post") as post_mock,
        ):
            post_mock.return_value = MagicMock()
            composer.action_send_whatsapp()
        # Assertions
        self.assertEqual(len(capture.records), 1)
        channel.invalidate_recordset()
        self.assertTrue(channel.message_ids)

    def test_send_message_with_dynamic_button(self):
        ctx = {
            "default_res_model": self.partner._name,
            "default_res_id": self.partner.id,
            "default_number_field_name": "phone",
            "default_composition_mode": "comment",
            "default_gateway_id": self.gateway.id,
        }
        tmpl_with_vars_dynamic = self.env["mail.whatsapp.template"].create(
            {
                "name": "Dynamic Button",
                "category": "utility",
                "language": "es",
                "body": "Name: {{1}} · Tel: {{2}}",
                "gateway_id": self.gateway.id,
                "variable_ids": [Command.clear()],
                "state": "approved",
                "is_supported": True,
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        self.assertEqual(len(tmpl_with_vars_dynamic.variable_ids), 0)
        self.env["mail.whatsapp.template.variable"].create(
            {
                "name": "{{1}}",
                "line_type": "body",
                "template_id": tmpl_with_vars_dynamic.id,
                "field_name": "name",
            }
        )
        self.env["mail.whatsapp.template.variable"].create(
            {
                "name": "{{2}}",
                "line_type": "body",
                "template_id": tmpl_with_vars_dynamic.id,
                "field_name": "phone",
            }
        )
        self.env["mail.whatsapp.template.button"].create(
            {
                "name": "1",
                "button_type": "url",
                "url_type": "dynamic",
                "template_id": tmpl_with_vars_dynamic.id,
                "website_url": "https://www.odoo.com",
            }
        )
        self.assertEqual(len(tmpl_with_vars_dynamic.variable_ids), 3)
        button = tmpl_with_vars_dynamic.variable_ids.search(
            [
                ("line_type", "=", "button"),
                ("template_id", "=", tmpl_with_vars_dynamic.id),
            ]
        )
        button.field_name = "name"
        self.gateway.whatsapp_account_id = "123456"
        form_composer = Form(self.env["whatsapp.composer"].with_context(**ctx))
        form_composer.template_id = tmpl_with_vars_dynamic
        self.assertTrue(form_composer.is_required_template)
        self.assertTrue(form_composer._get_modifier("template_id", "required"))
        composer = form_composer.save()
        channel = self.partner._whatsapp_get_channel(
            composer.number_field_name, composer.gateway_id
        )
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post") as post_mock,
        ):
            post_mock.return_value = MagicMock()
            composer.action_send_whatsapp()
        # Assertions
        self.assertEqual(len(capture.records), 1)
        channel.invalidate_recordset()
        self.assertTrue(channel.message_ids)

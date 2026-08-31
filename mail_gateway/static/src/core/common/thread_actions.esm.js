import {_t} from "@web/core/l10n/translation";
import {reactive} from "@odoo/owl";
import {registerThreadAction} from "@mail/core/common/thread_actions";

// The lookups below cannot store their result on the Thread record: in Odoo 19
// Thread is a reactive Record, and assigning undeclared properties to it from
// inside `condition()` (which runs during render) corrupts the record and the
// whole thread stops rendering -- no message is drawn at all, silently.
// Keep the cache outside the record; `reactive` still re-renders on write.
// undefined = not looked up yet, null = looked up, nothing found.
const gwCache = reactive({guest: {}, partner: {}});
const inFlight = new Set();

function lookupOnce(key, fn) {
    if (inFlight.has(key)) {
        return;
    }
    inFlight.add(key);
    Promise.resolve(fn()).finally(() => inFlight.delete(key));
}

// Odoo 19: action definitions receive a params object ({owner, thread, store,
// action}) instead of the owner component.
registerThreadAction("open-gw-new-partner", {
    condition({owner, thread}) {
        if (
            thread?.model !== "discuss.channel" ||
            (owner.props.chatWindow && !owner.props.chatWindow.isOpen)
        ) {
            return false;
        }
        const cached = gwCache.guest[thread.id];
        if (cached !== undefined) {
            return Boolean(cached);
        }
        const orm = owner.env.services.orm;
        lookupOnce(`guest-${thread.id}`, async () => {
            const members = await orm.silent.searchRead(
                "discuss.channel.member",
                [["channel_id", "=", thread.id]],
                ["guest_id"]
            );
            const guestMembers = members.filter((m) => m.guest_id);
            gwCache.guest[thread.id] =
                guestMembers.length === 1 ? guestMembers[0].guest_id : null;
        });
        return false;
    },
    icon: "fa fa-fw fa-address-book",
    name: _t("New Partner"),
    async open({owner, thread}) {
        const guestId = gwCache.guest[thread.id];
        if (!guestId) {
            return;
        }
        await owner.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mail.guest.manage",
            context: {default_guest_id: guestId[0]},
            views: [[false, "form"]],
            target: "new",
        });
    },
    sequence: 18,
});
registerThreadAction("open-gw-profile", {
    condition({owner, thread}) {
        // Check basic conditions
        if (
            thread?.model !== "discuss.channel" ||
            (owner.props.chatWindow && !owner.props.chatWindow.isOpen)
        ) {
            return false;
        }
        const cachedPartner = gwCache.partner[thread.id];
        if (cachedPartner !== undefined) {
            return Boolean(cachedPartner);
        }
        const orm = owner.env.services.orm;
        let partnerId = null;
        lookupOnce(`partner-${thread.id}`, async () => {
            const channelData = await orm.silent.searchRead(
                "discuss.channel",
                [["id", "=", thread.id]],
                ["gateway_channel_token"]
            );
            if (channelData[0]?.gateway_channel_token) {
                const gatewayChannel = await orm.silent.searchRead(
                    "res.partner.gateway.channel",
                    [["gateway_token", "=", channelData[0].gateway_channel_token]],
                    ["partner_id"]
                );
                partnerId = Array.isArray(gatewayChannel[0]?.partner_id)
                    ? gatewayChannel[0].partner_id[0]
                    : gatewayChannel[0]?.partner_id;
            } else {
                // Odoo 19: `correspondent` is a discuss.channel.member whose
                // `persona` getter returns its res.partner or mail.guest.
                partnerId = thread.correspondent?.partner_id?.id;
            }
            gwCache.partner[thread.id] = partnerId ?? null;
        });
        return false;
    },
    icon: "fa fa-fw fa-user-circle-o",
    name: _t("Open Contact"),
    async open({owner, thread}) {
        const partnerId = gwCache.partner[thread.id];
        await owner.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partnerId,
            views: [[false, "form"]],
        });
    },
    sequence: 17,
});

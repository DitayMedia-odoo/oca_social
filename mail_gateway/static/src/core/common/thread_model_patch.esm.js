import {assignIn} from "@mail/utils/common/misc";
import {fields} from "@mail/core/common/record";
import {imageUrl} from "@web/core/utils/urls";
import {Thread} from "@mail/core/common/thread_model";
import {patch} from "@web/core/utils/patch";

patch(Thread, {
    _insert(data) {
        const thread = super._insert(...arguments);
        if (thread.type === "gateway") {
            assignIn(thread, data, ["anonymous_name", "gateway"]);
            this.store.discuss.gateway.threads.add(thread);
        }
        return thread;
    },
});

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.gateway = fields.One("Gateway");
        this.operator = fields.One("res.partner");
        this.gateway_notifications = [];
        this.gateway_followers = fields.Many("res.partner");
    },
    get isChatChannel() {
        return this.channel_type === "gateway" || super.isChatChannel;
    },
    get hasMemberList() {
        return this.channel_type === "gateway" || super.hasMemberList;
    },
    get avatarUrl() {
        if (this.channel_type !== "gateway") {
            return super.avatarUrl;
        }
        return imageUrl("discuss.channel", this.id, "avatar_128", {
            unique: this.avatar_cache_key,
        });
    },
    /** @param {Object} data */
    update(data) {
        super.update(data);
        if ("gateway_id" in data && this.channel_type === "gateway") {
            this.gateway = data.gateway_id;
        }
    },
    _computeDiscussAppCategory() {
        if (this.channel_type === "gateway") {
            return this.store.discuss.gateway;
        }
        return super._computeDiscussAppCategory(...arguments);
    },
});

import {Message} from "@mail/core/common/message_model";
import {patch} from "@web/core/utils/patch";
import {router} from "@web/core/browser/router";
import {url} from "@web/core/utils/urls";

patch(Message.prototype, {
    setup() {
        super.setup(...arguments);
        this.gateway_thread_data = {};
    },
    get resUrl() {
        // The server always sends a (possibly empty) dict, so the presence of
        // the key is not enough to know the message comes from a gateway.
        if (!this.gateway_thread_data?.model) {
            return super.resUrl;
        }
        return url(
            router.stateToUrl({
                model: this.gateway_thread_data.model,
                resId: this.gateway_thread_data.id,
            })
        );
    },
    get editable() {
        return super.editable && !this.gateway_type;
    },
});

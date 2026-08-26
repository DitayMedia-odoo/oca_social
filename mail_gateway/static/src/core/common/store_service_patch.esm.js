import {Store} from "@mail/core/common/store_service";
import {patch} from "@web/core/utils/patch";

patch(Store.prototype, {
    async getMessagePostParams(params) {
        const post_params = await super.getMessagePostParams(...arguments);
        if (params.thread.gateway_notifications) {
            post_params.post_data.gateway_notifications =
                params.thread.gateway_notifications;
        }
        return post_params;
    },
});
